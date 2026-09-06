# run_program.py

from subprocess import run, CalledProcessError


def git_commit_needed():
    stdout = run_program(["git", "status"])
    return "needs commit" in parse_git(stdout)

def parse_git(stdout):
    r'''Returns set of "needs commit", "needs -a", "needs push".

    Or empty set if no action needed.
    '''
    flags = set()
    for section in stdout.split("\n\n"):
        if section.startswith("On branch main\n"):
            lines = section.split('\n')
            if lines[1].startswith("Your branch is up to date"):
                continue
            if lines[1].startswith("Your branch is ahead"):
                flags.add("needs push")
                continue
            raise ValueError(f"Unknown second line to 'On branch main': {line[1]}")
        if section.startswith("Changes to be committed:\n"):
            flags.add("needs commit")
            continue
        if section.startswith("Changes not staged for commit:\n"):
            flags.add("needs commit")
            flags.add("needs -a")
            continue
        if section.startswith("no changes added to commit, working tree clean\n"):
            flags.add("needs commit")
            flags.add("needs -a")
            continue
        if section.startswith("nothing added to commit but untracked files present\n"):
            continue
        if section.startswith("nothing to commit, working tree clean\n"):
            continue
        # let Untracked files: fall through, needs manual intervention
        raise ValueError(f"Unknown git output: {section.split("\n")[0]}")
    return flags

def git_commit(message):
    run_program(["git", "commit", "-a", "-m", message])

def git_push_needed():
    stdout = run_program(["git", "status"])
    push_needed = False
    for section in stdout.split("\n\n"):
        if section.startswith("On branch main\n"):
            continue
        if section.startswith("nothing to commit, working tree clean\n"):
            continue
        raise ValueError(section.split("\n")[0])
    return push_needed

def git_push():
    run_program(["git", "push"])

def print_file(filename):
    run_program(["lp", filename])

def run_program(command):
    try:
        cp = run(command, capture_output=True, text=True, check=True)
    except CalledProcessError as exc:
        if exc.stdout:
            print("stdout:", exc.stdout)
        if exc.stderr:
            raise ValueError(exc.stderr)
        raise ValueError(f"{command} failed with {exc.returncode}")
    if cp.stderr:
        raise ValueError(cp.stderr)
    return cp.stdout


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--commit_needed", "-c", action="store_true", default=False)
    parser.add_argument("--commit", "-C")
    parser.add_argument("--push_needed", "-p", action="store_true", default=False)
    parser.add_argument("--push", "-P", action="store_true", default=False)
    parser.add_argument("--print", "-T")
    parser.add_argument("--test", "-t", default=(), help="command", nargs="+")
    args = parser.parse_args()

    if args.commit_needed:
        git_commit_needed()
    elif args.commit:
        print("commit:", args.commit)
        git_commit(args.commit)
    elif args.push_needed:
        git_push_needed()
    elif args.push:
        git_push()
    elif args.print:
        print("print:", args.print)
        print_file(args.print)
    elif args.test:
        command = args.test
        print("run:", command)
        stdout = run_program(command)
        print(stdout)
