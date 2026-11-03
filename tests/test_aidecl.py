import json
import subprocess
from pathlib import Path

import pytest

from aidecl import inline
from aidecl.cli import main
from aidecl.config import ConfigError, load
from aidecl.globbing import matches
from aidecl.model import Declaration, validate
from aidecl.project import Project


def write(root: Path, rel: str, text: str = "x\n") -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")
    return p


FULL_G0 = 'AI-Generation = "G0"\nAI-Verification = "V0"\nTested-by = "Jane"\n'
FULL_G2 = ('AI-Generation = "G2"\nAI-Verification = "V3"\nAssisted-by = ["Model A"]\n'
           'Verified-by = "Model B, fresh session"\nTested-by = "Jane"\n')


# ------------------------------------------------------------------ globbing
@pytest.mark.parametrize("pattern,path,expected", [
    ("*.jl", "a.jl", True),
    ("*.jl", "src/a.jl", False),
    ("**/*.jl", "a.jl", True),
    ("**/*.jl", "src/deep/a.jl", True),
    ("src/**", "src/a/b.jl", True),
    ("src/**", "srcx/a.jl", False),
    ("**", "anything/at/all.txt", True),
    ("results/run?.csv", "results/run1.csv", True),
    ("results/run?.csv", "results/run10.csv", False),
    ("data/\\*.csv", "data/*.csv", True),
    ("data/\\*.csv", "data/a.csv", False),
    ("./README.md", "README.md", True),
])
def test_glob(pattern, path, expected):
    assert matches(pattern, path) is expected


# ------------------------------------------------------------------ rules
@pytest.mark.parametrize("values,ok", [
    ({"AI-Generation": "G0", "AI-Verification": "V0", "Tested-by": "J"}, True),
    ({"AI-Generation": "G0", "AI-Verification": "V0"}, False),                       # V0 needs Tested-by
    ({"AI-Generation": "G1", "AI-Verification": "V0", "Tested-by": "J"}, False),     # G1 needs Assisted-by
    ({"AI-Generation": "G0", "AI-Verification": "V0", "Tested-by": "J", "Assisted-by": "X"}, False),
    ({"AI-Generation": "G3", "AI-Verification": "V1", "Assisted-by": "X", "Verified-by": "X'"}, True),
    ({"AI-Generation": "G3", "AI-Verification": "V2", "Assisted-by": "X"}, False),   # V2 needs Verified-by
    ({"AI-Generation": "G2", "AI-Verification": "V3", "Assisted-by": "X", "Verified-by": "Y"}, False),
    ({"AI-Generation": "G2", "AI-Verification": "V3", "Assisted-by": "X", "Verified-by": "Y", "Tested-by": "J"}, True),
    ({"AI-Generation": "G4", "AI-Verification": "V0", "Tested-by": "J"}, False),
])
def test_rules(values, ok):
    assert (validate(Declaration.from_mapping(values, "test")) == []) is ok


def test_no_declaration():
    assert validate(Declaration()) == ["no declaration (not matched by AIDECL.toml and no inline tags)"]


# ------------------------------------------------------------------ config
def test_config_errors(tmp_path):
    bad = {
        'version = 2\n': "version = 1",
        'version = 1\nfoo = 1\n': "unknown top-level",
        'version = 1\n[[annotations]]\nAI-Generation = "G0"\n': "'path' is required",
        'version = 1\n[[annotations]]\npath = "**"\nAI-Generation = "G7"\n': "invalid AI-Generation",
        'version = 1\n[[annotations]]\npath = "**"\nLicense = "MIT"\n': "unknown key",
        'version = 1\n[[annotations]]\npath = "**"\nprecedence = "aggregate"\n': "precedence",
        'version = 1\n[[annotations]\n': "invalid TOML",
    }
    for text, message in bad.items():
        (tmp_path / "AIDECL.toml").write_text(text)
        with pytest.raises(ConfigError, match=message):
            load(tmp_path)


def test_last_annotation_wins(tmp_path):
    write(tmp_path, "AIDECL.toml", f'version = 1\n[[annotations]]\npath = "**"\n{FULL_G0}'
                                  f'[[annotations]]\npath = "src/**"\n{FULL_G2}')
    write(tmp_path, "README.md")
    write(tmp_path, "src/a.jl")
    res = {r.path: r for r in Project(tmp_path).results()}
    assert res["README.md"].declaration.generation == "G0"
    assert res["src/a.jl"].declaration.generation == "G2"
    assert res["src/a.jl"].declaration.source == "AIDECL.toml [2]"
    assert all(not r.errors for r in res.values())
    assert "AIDECL.toml" not in res


def test_exclude(tmp_path):
    write(tmp_path, "AIDECL.toml", f'version = 1\nexclude = ["build/**"]\n[[annotations]]\npath = "*.md"\n{FULL_G0}')
    write(tmp_path, "README.md")
    write(tmp_path, "build/out.html")
    assert [r.path for r in Project(tmp_path).results()] == ["README.md"]


# ------------------------------------------------------------------ inline
def test_inline_closest_and_override(tmp_path):
    write(tmp_path, "AIDECL.toml", f'version = 1\n[[annotations]]\npath = "**"\n{FULL_G0}'
                                  f'[[annotations]]\npath = "locked/**"\nprecedence = "override"\n{FULL_G0}')
    header = "# AI-Generation: G2\n# AI-Verification: V3\n# Assisted-by: A\n# Verified-by: B\n# Tested-by: J\n"
    write(tmp_path, "src/a.jl", header + "f(x) = x\n")
    write(tmp_path, "locked/b.jl", header + "g(x) = x\n")
    res = {r.path: r.declaration for r in Project(tmp_path).results()}
    assert (res["src/a.jl"].generation, res["src/a.jl"].source) == ("G2", "inline")
    assert (res["locked/b.jl"].generation, res["locked/b.jl"].source) == ("G0", "AIDECL.toml [2]")


@pytest.mark.parametrize("name,line,found", [
    ("f.jl", "# AI-Generation: G1", True),
    ("f.jl", "#= AI-Generation: G1 =#", True),
    ("f.rs", "// AI-Generation: G1", True),
    ("f.c", "/* AI-Generation: G1 */", True),
    ("f.tex", "% AI-Generation: G1", True),
    ("f.lua", "-- AI-Generation: G1", True),
    ("f.md", "<!-- AI-Generation: G1 -->", True),
    ("f.md", "# AI-Generation: G1", False),        # '#' is a heading in Markdown
    ("f.jl", "// AI-Generation: G1", False),       # not Julia comment syntax
    ("f.jl", "AI-Generation: G1", False),          # not a comment
    ("f.jl", "    # AI-Generation: G1", False),    # indented
    ("f.jl", "x = 1  # AI-Generation: G1", False), # trailing comment after code
    ("f.txt", "# AI-Generation: G1", False),       # unknown file type: AIDECL.toml only
    ("LICENSE", "-- AI-Generation: G1", False),
])
def test_inline_needs_comment(tmp_path, name, line, found):
    p = write(tmp_path, name, line + "\n")
    d = inline.parse(p)
    assert (d is not None and d.generation == "G1") is found


def test_inline_ignores_documentation(tmp_path):
    # '#' in a Markdown code block is not a comment in Markdown
    md = write(tmp_path, "README.md", "# Pkg\n\n```julia\n# AI-Generation: G2\n# AI-Verification: V0\n```\n")
    assert inline.parse(md) is None
    # indented example in a docstring
    py = write(tmp_path, "m.py", '"""Example:\n\n    # AI-Generation: G2\n    # AI-Verification: V3\n"""\n')
    assert inline.parse(py) is None
    # explanatory comment without a valid level is not a declaration
    yml = write(tmp_path, "w.yml", "# Rules:\n#   AI-Generation: G0-G3   always\n#   Assisted-by: required for G1-G3\n")
    assert inline.parse(yml) is None


def test_inline_block_must_be_contiguous(tmp_path):
    p = write(tmp_path, "f.jl", "# AI-Generation: G1\n# AI-Verification: V0\n# Tested-by: J\n\n# Assisted-by: X\n")
    d = inline.parse(p)
    assert d.generation == "G1" and d.assisted_by == ()     # the separated line doesn't belong to it
    assert validate(d) == ["G1 needs Assisted-by (tool and model)"]


def test_inline_two_blocks(tmp_path):
    p = write(tmp_path, "f.jl", "# AI-Generation: G1\n\n# AI-Generation: G2\n")
    assert "more than one inline declaration block" in inline.parse(p).problems


def test_inline_c_block_comment(tmp_path):
    p = write(tmp_path, "k.c", "/*\n * AI-Generation: G1\n * AI-Verification: V1\n * Assisted-by: X\n"
                               " * Verified-by: X, fresh session\n */\nint main(){}\n")
    d = inline.parse(p)
    assert (d.generation, d.verification, d.verified_by) == ("G1", "V1", ("X, fresh session",))
    assert validate(d) == []


def test_inline_only_header(tmp_path):
    p = write(tmp_path, "f.jl", "\n" * 40 + "# AI-Generation: G1\n")
    assert inline.parse(p) is None


def test_inline_binary_ignored(tmp_path):
    p = tmp_path / "data.bin"
    p.write_bytes(b"\x00\x01# AI-Generation: G1\n")
    assert inline.parse(p) is None


def test_inline_duplicate(tmp_path):
    p = write(tmp_path, "f.py", "# AI-Generation: G1\n# AI-Generation: G2\n")
    assert "more than once" in inline.parse(p).problems[0]


def test_inline_write_roundtrip(tmp_path):
    p = write(tmp_path, "run.sh", "#!/bin/bash\necho hi\n")
    values = {"AI-Generation": "G1", "AI-Verification": "V0", "Assisted-by": ["Copilot"], "Tested-by": ["J"]}
    inline.write(p, values)
    text = p.read_text()
    assert text.startswith("#!/bin/bash\n# AI-Generation: G1\n")
    assert text.endswith("\necho hi\n")
    # rewriting replaces instead of duplicating
    inline.write(p, {**values, "AI-Generation": "G2"})
    d = inline.parse(p)
    assert d.generation == "G2" and d.problems == []
    assert p.read_text().count("AI-Generation") == 1


def test_inline_write_front_matter_and_markdown(tmp_path):
    p = write(tmp_path, "post.md", "---\ntitle: x\n---\n# Heading\n")
    inline.write(p, {"AI-Generation": "G0", "AI-Verification": "V0", "Tested-by": ["J"]})
    lines = p.read_text().splitlines()
    assert lines[:3] == ["---", "title: x", "---"]
    assert lines[3] == "<!-- AI-Generation: G0 -->"
    assert inline.parse(p).generation == "G0"


def test_inline_write_unknown_type(tmp_path):
    p = write(tmp_path, "results.csv", "a,b\n")
    with pytest.raises(ValueError, match="AIDECL.toml"):
        inline.write(p, {"AI-Generation": "G0"})


# ------------------------------------------------------------------ git integration
def test_git_respects_gitignore(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write(tmp_path, ".gitignore", "*.log\n")
    write(tmp_path, "a.jl")
    write(tmp_path, "debug.log")
    write(tmp_path, "AIDECL.toml", f'version = 1\n[[annotations]]\npath = "**"\n{FULL_G0}')
    paths = [r.path for r in Project(tmp_path).results()]
    assert paths == [".gitignore", "a.jl"]


# ------------------------------------------------------------------ CLI
def test_cli_workflow(tmp_path, capsys):
    root = str(tmp_path)
    write(tmp_path, "src/solver.jl")
    write(tmp_path, "results/run1.csv")
    write(tmp_path, "README.md")

    assert main(["--root", root, "lint"]) == 1                      # nothing declared yet
    assert main(["--root", root, "init", "-g", "G0", "-v", "V0", "--tested-by", "Jane"]) == 0
    assert main(["--root", root, "lint"]) == 0
    assert main(["--root", root, "init"]) == 2                      # refuses to overwrite

    # incomplete declarations are refused before anything is written
    assert main(["--root", root, "annotate", "results/**", "-g", "G2", "-v", "V1"]) == 2
    assert main(["--root", root, "annotate", "results/**", "-g", "G2", "-v", "V1",
                 "--assisted-by", "Model A", "--verified-by", "Model A, fresh session"]) == 0
    load(tmp_path)  # still valid TOML
    capsys.readouterr()
    assert main(["--root", root, "report", "--json"]) == 0
    data = {d["path"]: d for d in json.loads(capsys.readouterr().out)}
    assert data["results/run1.csv"]["AI-Generation"] == "G2"
    assert data["src/solver.jl"]["AI-Generation"] == "G0"

    out = tmp_path / "badges"
    assert main(["--root", root, "badge", "--out", str(out)]) == 0
    gen = json.loads((out / "aidecl-generation.json").read_text())
    assert gen["message"] == "G0 67% · G2 33%"
    ver = json.loads((out / "aidecl-verification.json").read_text())
    assert ver["message"] == "V0 67% · V1 33%"


def test_cli_annotate_directory_and_quotes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "notebooks/a.ipynb", "{}")
    assert main(["annotate", "notebooks", "-g", "G1", "-v", "V0",
                 "--assisted-by", 'Model "X" \\ beta', "--tested-by", "Jürgen"]) == 0
    cfg = load(tmp_path)
    a = cfg.annotations[0]
    assert a.paths == ("notebooks/**",)
    assert a.values["Assisted-by"] == ('Model "X" \\ beta',)
    assert a.values["Tested-by"] == ("Jürgen",)


def test_lint_reports_undeclared_and_unused(tmp_path, capsys):
    write(tmp_path, "AIDECL.toml", f'version = 1\n[[annotations]]\npath = "*.md"\n{FULL_G0}'
                                  f'[[annotations]]\npath = "nothing/**"\n{FULL_G0}')
    write(tmp_path, "README.md")
    write(tmp_path, "src/a.jl")
    assert main(["--root", str(tmp_path), "lint"]) == 1
    out = capsys.readouterr().out
    assert "no declaration" in out and "src/a.jl" in out
    assert "annotation [2] matches no file" in out
    write(tmp_path, "AIDECL.toml", f'version = 1\n[[annotations]]\npath = "**"\n{FULL_G0}'
                                  f'[[annotations]]\npath = "nothing/**"\n{FULL_G0}')
    assert main(["--root", str(tmp_path), "lint"]) == 0
    assert main(["--root", str(tmp_path), "lint", "--strict"]) == 1


# ------------------------------------------------------------------ regressions from the independent review
from aidecl.cli import badge_json, percentages  # noqa: E402
from collections import Counter  # noqa: E402


@pytest.mark.parametrize("counts", [
    dict(G0=4, G1=30, G2=39, G3=39, undeclared=1),
    dict(G1=3, G2=38, G3=38, undeclared=1),
    dict(G0=1, G1=1, G2=1),
    dict(G0=1, G1=998),
])
def test_percentages_sum_and_sign(counts):
    pct = percentages(counts)
    assert sum(pct.values()) == 100 and min(pct.values()) >= 0


def test_badge_small_share_shown():
    msg = badge_json("x", Counter(G0=1, G1=998), ["G0", "G1"], "000")["message"]
    assert msg == "G0 <1% · G1 100%"


def test_inline_write_keeps_crlf_bom_and_other_breaks(tmp_path):
    p = tmp_path / "a.py"
    p.write_bytes("﻿#!x\r\ns = 'a b'\r\nform\ffeed\r\n".encode())
    values = {"AI-Generation": "G0", "AI-Verification": "V0", "Tested-by": ["J"]}
    inline.write(p, values)
    out = p.read_bytes().decode()
    assert out.startswith("﻿#!x\r\n# AI-Generation: G0\r\n")
    assert "s = 'a b'\r\nform\ffeed\r\n" in out
    assert "\n" not in out.replace("\r\n", "")          # no bare LF introduced
    assert inline.parse(p).generation == "G0"           # BOM doesn't hide the first line


def test_inline_bom_first_line(tmp_path):
    p = tmp_path / "b.jl"
    p.write_bytes("﻿# AI-Generation: G0\n# AI-Verification: V0\n# Tested-by: J\n".encode())
    assert validate(inline.parse(p)) == []


def test_yaml_documents_are_not_front_matter(tmp_path):
    p = write(tmp_path, "multi.yml", "---\n" + "".join(f"k{i}: {i}\n" for i in range(35)) + "---\nz: 1\n")
    inline.write(p, {"AI-Generation": "G0", "AI-Verification": "V0", "Tested-by": ["J"]})
    assert p.read_text().startswith("# AI-Generation: G0\n")
    inline.write(p, {"AI-Generation": "G1", "AI-Verification": "V0", "Tested-by": ["J"], "Assisted-by": ["X"]})
    assert p.read_text().count("AI-Generation") == 1 and inline.parse(p).generation == "G1"


def test_long_front_matter_is_refused(tmp_path):
    p = write(tmp_path, "post.md", "---\n" + "a: 1\n" * 40 + "---\ntext\n")
    before = p.read_bytes()
    with pytest.raises(ValueError, match="AIDECL.toml"):
        inline.write(p, {"AI-Generation": "G0", "AI-Verification": "V0", "Tested-by": ["J"]})
    assert p.read_bytes() == before


def test_markdown_fenced_html_comment_ignored(tmp_path):
    p = write(tmp_path, "README.md", "# X\n\n```markdown\n<!-- AI-Generation: G2 -->\n<!-- AI-Verification: V0 -->\n```\n")
    assert inline.parse(p) is None


def test_annotate_keeps_escapes_and_escapes_literals(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "what?.txt")
    write(tmp_path, "whatZ.txt")
    write(tmp_path, "star*.txt")
    args = ["-g", "G0", "-v", "V0", "--tested-by", "J"]
    assert main(["annotate", "what?.txt", *args]) == 0              # existing file: matched exactly
    assert main(["annotate", "star\\*.txt", *args]) == 0            # escaped glob kept as is
    paths = [a.paths[0] for a in load(tmp_path).annotations]
    assert paths == ["what\\?.txt", "star\\*.txt"]
    res = {r.path: r.declaration.source for r in Project(tmp_path).results()}
    assert res["whatZ.txt"] == "none" and res["star*.txt"] == "AIDECL.toml [2]"
    # an existing file name given without glob characters matches only itself
    write(tmp_path, "a[1].txt")
    assert main(["annotate", "a[1].txt", *args]) == 0
    assert load(tmp_path).annotations[-1].paths == ("a[1].txt",)


def test_annotate_glob_relative_to_cwd(tmp_path, monkeypatch):
    write(tmp_path, "top.jl")
    write(tmp_path, "sub/inner.jl")
    monkeypatch.chdir(tmp_path / "sub")
    assert main(["--root", "..", "annotate", "*.jl", "-g", "G0", "-v", "V0", "--tested-by", "J"]) == 0
    assert load(tmp_path).annotations[0].paths == ("sub/*.jl",)


def test_annotate_symlink_not_followed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    write(tmp_path, "real/t.txt")
    (tmp_path / "lnk.txt").symlink_to("real/t.txt")
    assert main(["annotate", "lnk.txt", "-g", "G0", "-v", "V0", "--tested-by", "J"]) == 0
    assert load(tmp_path).annotations[0].paths == ("lnk.txt",)


@pytest.mark.parametrize("bad", ["a\x7fb", "Jane\nimport os", "  "])
def test_annotate_rejects_control_characters(tmp_path, bad):
    write(tmp_path, "a.py", "x = 1\n")
    assert main(["--root", str(tmp_path), "annotate", str(tmp_path / "a.py"), "-g", "G0", "-v", "V0",
                 "--tested-by", bad]) == 2
    assert not (tmp_path / "AIDECL.toml").exists()
    assert main(["annotate", str(tmp_path / "a.py"), "--inline", "-g", "G0", "-v", "V0", "--tested-by", bad]) == 2
    assert (tmp_path / "a.py").read_text() == "x = 1\n"


def test_inline_with_precedence_refused(tmp_path):
    write(tmp_path, "a.py", "x = 1\n")
    assert main(["annotate", str(tmp_path / "a.py"), "--inline", "--precedence", "override",
                 "-g", "G0", "-v", "V0", "--tested-by", "J"]) == 2


def test_lint_missing_root_and_empty(tmp_path):
    assert main(["--root", str(tmp_path / "missing"), "lint"]) == 2
    assert main(["--root", str(tmp_path), "lint"]) == 1                 # no files at all
    assert main(["--root", str(tmp_path / "missing"), "init"]) == 2


def test_git_failure_is_an_error(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()                                          # broken repository
    write(tmp_path, "a.txt")
    assert main(["--root", str(tmp_path), "lint"]) == 2


@pytest.mark.parametrize("text,message", [
    ("version = true\n", "version = 1"),
    ("version = 1\nannotations = [1]\n", "annotations"),
    ('version = 1\n[[annotations]]\npath = []\n', "must not be empty"),
    ('version = 1\n[[annotations]]\npath = "**"\nAI-Generation = "G0"\nai-generation = "G1"\n', "more than once"),
])
def test_more_config_errors(tmp_path, text, message):
    (tmp_path / "AIDECL.toml").write_text(text)
    with pytest.raises(ConfigError, match=message):
        load(tmp_path)


def test_closest_fills_missing_axis(tmp_path):
    write(tmp_path, "AIDECL.toml", f'version = 1\n[[annotations]]\npath = "**"\n{FULL_G2}')
    write(tmp_path, "a.jl", "# AI-Verification: V0\n# Tested-by: Bob\n\nf() = 1\n")
    (r,) = [r for r in Project(tmp_path).results() if r.path == "a.jl"]
    d = r.declaration
    assert (d.generation, d.assisted_by) == ("G2", ("Model A",))       # generation axis from AIDECL.toml
    assert (d.verification, d.verified_by, d.tested_by) == ("V0", (), ("Bob",))  # verification axis inline
    assert r.errors == [] and d.source == "inline + AIDECL.toml [1]"


def test_report_and_badge_agree(tmp_path, capsys):
    write(tmp_path, "AIDECL.toml", 'version = 1\n[[annotations]]\npath = "**"\nAI-Generation = "G2"\n'
                                   'AI-Verification = "V0"\nTested-by = "J"\n')   # G2 without Assisted-by
    write(tmp_path, "a.txt")
    assert main(["--root", str(tmp_path), "report"]) == 0
    assert "undeclared" in capsys.readouterr().out
    assert main(["--root", str(tmp_path), "badge", "--out", str(tmp_path / "b")]) == 0
    assert "undeclared 100%" in (tmp_path / "b" / "aidecl-generation.json").read_text()


# ------------------------------------------------------------------ regressions from the second review
def test_inline_header_must_fit_completely(tmp_path):
    values = {"AI-Generation": "G2", "AI-Verification": "V1", "Assisted-by": ["C"], "Verified-by": ["O"]}
    p = write(tmp_path, "edge.md", "---\n" + "a: 1\n" * 26 + "---\ntext\n")   # front matter ends at line 28
    before = p.read_bytes()
    with pytest.raises(ValueError, match="first 30 lines"):
        inline.write(p, values)
    assert p.read_bytes() == before
    # replacing a block near the limit with a longer one is refused too
    q = write(tmp_path, "late.py", "x = 1\n" * 27 + "# AI-Generation: G0\n# AI-Verification: V0\n# Tested-by: J\n")
    before = q.read_bytes()
    with pytest.raises(ValueError):
        inline.write(q, {"AI-Generation": "G2", "AI-Verification": "V3", "Assisted-by": ["C"],
                         "Verified-by": ["O"], "Tested-by": ["J"]})
    assert q.read_bytes() == before


def test_annotate_bad_globs_refused(tmp_path, monkeypatch):
    write(tmp_path, "top.jl")
    write(tmp_path, "sub/inner.jl")
    monkeypatch.chdir(tmp_path / "sub")
    args = ["-g", "G0", "-v", "V0", "--tested-by", "J"]
    assert main(["--root", "..", "annotate", "../*.jl", *args]) == 2
    assert main(["--root", "..", "annotate", str(tmp_path) + "/*.jl", *args]) == 2
    assert main(["--root", "..", "annotate", "missing.jl", *args]) == 2       # typo, no glob
    assert not (tmp_path / "AIDECL.toml").exists()


def test_annotate_through_symlinked_root(tmp_path, monkeypatch):
    real = tmp_path / "real"
    write(real, "sub/a.jl")
    (tmp_path / "link").symlink_to(real)
    monkeypatch.chdir(tmp_path / "link" / "sub")
    args = ["-g", "G0", "-v", "V0", "--tested-by", "J"]
    assert main(["--root", str(tmp_path / "link"), "annotate", "*.jl", *args]) == 0
    assert main(["--root", str(tmp_path / "link"), "annotate", "a.jl", *args]) == 0
    assert main(["--root", str(tmp_path / "link"), "annotate", str(tmp_path / "link"), *args]) == 0
    assert [a.paths[0] for a in load(real).annotations] == ["sub/*.jl", "sub/a.jl", "**"]


def test_inline_stray_list_keys_are_errors(tmp_path):
    write(tmp_path, "AIDECL.toml", f'version = 1\n[[annotations]]\npath = "**"\n{FULL_G0}')
    write(tmp_path, "a.jl", "# AI-Verification: V0\n# Tested-by: J\n# Assisted-by: Copilot\n")
    (r,) = [r for r in Project(tmp_path).results() if r.path == "a.jl"]
    assert "inline Assisted-by without an inline AI-Generation line" in r.errors


def test_markdown_mismatched_fence(tmp_path):
    p = write(tmp_path, "r.md", "```\n~~~\n<!-- AI-Generation: G2 -->\n<!-- AI-Verification: V0 -->\n```\n")
    assert inline.parse(p) is None          # ~~~ does not close a ``` fence
