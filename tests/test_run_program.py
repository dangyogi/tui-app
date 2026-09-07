# test_run_program.py

import pytest
from tui_app.run_program import parse_git


def align(text):
    lines = text.split('\n')
    if not lines[0] or lines[0].isspace():
        del lines[0]
    skip = len(lines[0]) - len(lines[0].lstrip())
    return '\n'.join(l[skip:] for l in lines)

Sections = dict(
    line1=align("""
      On branch main
      Your branch is up to date with 'origin/main'."""),
    line2=align("""
      On branch main
      Your branch is ahead of 'origin/main' by 1 commit.
        (use "git push" to publish your local commits)"""),
    new_file=align("""
      Changes to be committed:
        (use "git restore --staged <file>..." to unstage)
      \tnew file:   foobar"""),
    deleted=align("""
      Changes to be committed:
        (use "git restore --staged <file>..." to unstage)
      \tdeleted:    tui.py"""),
    not_staged=align("""
      Changes not staged for commit:
        (use "git add <file>..." to update what will be committed)
        (use "git restore <file>..." to discard changes in working directory)
      \tmodified:   actions.py"""),
    not_staged2=align("""
      Changes not staged for commit:
        (use "git add <file>..." to update what will be committed)
        (use "git restore <file>..." to discard changes in working directory)
      \tmodified:   actions.py
      \tmodified:   fungus.py"""),
    untracked=align("""
      Untracked files:
        (use "git add <file>..." to include in what will be committed)
      \tfoobar"""),

    # neither of these appear if "Changes to be committed" is present, regardless of "Changes not staged"
    no_changes='no changes added to commit (use "git add" and/or "git commit -a")',
    nothing_untracked='nothing added to commit but untracked files present (use "git add" to track)',

    nothing_to_commit='nothing to commit, working tree clean',

    unknown0='none of the above blank',
    unknown1=align("""
      none of the above:
        try again"""),
)

@pytest.mark.parametrize("name, body", [
    ('line1', "On branch main\nYour branch is up to date with 'origin/main'."),
    ('line2', "On branch main\nYour branch is ahead of 'origin/main' by 1 commit.\n"
              '  (use "git push" to publish your local commits)'),
    ('new_file', 'Changes to be committed:\n  (use "git restore --staged <file>..." to unstage)\n'
                 '\tnew file:   foobar'),
])
def test_Sections(name, body):
    assert Sections[name] == body


@pytest.mark.parametrize("sections, ok_files, results", [
    ('line1,not_staged,no_changes', None, 'needs commit,needs -a'),
    ('line2,not_staged,no_changes', None, 'needs commit,needs -a,needs push'),
    ('line1,nothing_to_commit', None, ''),
    ('line1,not_staged,no_changes', ('actions.py',), 'needs commit,needs -a'),
    ('line1,not_staged,no_changes', ('actions.py', 'foobar.py'), 'needs commit,needs -a'),
    ('line1,not_staged2,no_changes', ('actions.py', 'fungus.py'), 'needs commit,needs -a'),
    ('line1,not_staged2,no_changes', ('fungus.py', 'actions.py'), 'needs commit,needs -a'),
    ('line1,not_staged2,no_changes', ('actions.py', 'fungus.py', 'foobar.py'), 'needs commit,needs -a'),
])
def test_parse_git(sections, ok_files, results):
    if results:
        answer = set(results.split(','))
    else:
        answer = set()
    assert parse_git('\n\n'.join(Sections[s] for s in sections.split(',')), ok_files) == answer


@pytest.mark.parametrize("sections, bad_section", [
    ('line1,new_file', 'new_file'),
    ('line1,deleted', 'deleted'),
    ('line1,untracked,nothing_untracked', 'untracked'),
    ('line1,unknown0,no_changes', 'unknown0'),
    ('line1,unknown1,no_changes', 'unknown1'),
])
def test_parse_git_errors(sections, bad_section):
    with pytest.raises(ValueError) as exc:
        parse_git('\n\n'.join(Sections[s] for s in sections.split(',')))
    assert exc.value.args[0] == "Unknown git output: " + Sections[bad_section].split('\n')[0]


@pytest.mark.parametrize("sections, ok_files, bad_file", [
    ('line1,not_staged,no_changes', ('foobar.py'), 'actions.py'),
    ('line1,not_staged2,no_changes', ('actions.py', 'foobar.py'), 'fungus.py'),
    ('line1,not_staged2,no_changes', ('fungus.py', 'foobar.py'), 'actions.py'),
])
def test_parse_git_ok_files_errors(sections, ok_files, bad_file):
    with pytest.raises(ValueError) as exc:
        parse_git('\n\n'.join(Sections[s] for s in sections.split(',')), ok_files)
    assert exc.value.args[0] == "Unexpected modified: " + bad_file
