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


@pytest.mark.parametrize("sections, results", [
    ('line1 new_file', ['needs commit']),
])
def test_parse_git(sections, results):
    assert parse_git('\n\n'.join(Sections[s] for s in sections.split())) == set(results)
