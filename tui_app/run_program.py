# run_program.py

from subprocess import run, CalledProcessError


def git_status():
    r'''Returns set of "needs commit", "needs -a", "needs push".

    Or empty set if no action needed.
    '''
    stdout = run_program(["git", "status"])
    return parse_git(stdout)

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
       #if section.startswith("Changes to be committed:\n"):
       #    flags.add("needs commit")
       #    continue
        if section.startswith("Changes not staged for commit:\n"):
            flags.add("needs commit")
            flags.add("needs -a")
            continue
        if section.startswith("no changes added to commit"):
            continue
        if section.startswith("nothing added to commit but untracked files present"):
            continue
        if section.startswith("nothing to commit, working tree clean"):
            continue
        # let Untracked files: fall through, needs manual intervention
        raise ValueError(f"Unknown git output: {section.split("\n")[0]}")
    return flags

def git_commit(message):
    run_program(["git", "commit", "-a", "-m", message])

def git_push():
    # git push output looks like this:
    #
    # Enumerating objects: 11, done.
    # Counting objects: 100% (11/11), done.
    # Delta compression using up to 8 threads
    # Compressing objects: 100% (6/6), done.
    # Writing objects: 100% (6/6), 944 bytes | 944.00 KiB/s, done.
    # Total 6 (delta 5), reused 0 (delta 0), pack-reused 0
    # remote: Resolving deltas: 100% (5/5), completed with 5 local objects.
    # To github.com:dangyogi/tui-app.git
    #    b82274d..0c8cee0  main -> main
    #
    # the last 2 lines go to stderr.  The rest don't show up in stdout when stdout is redirected.
    out = run_program(["git", "push"])
    print(out)

def git_commit_push(message, notify_fn=print):
    status = git_status()
    push = "needs push" in status
    notify_message = ""
    def notify(text):
        nonlocal notify_message
        if notify_message:
            notify_message += "; " + text
        else:
            notify_message = text
        notify_fn(notify_message)
    if "needs commit" in git_status():
        notify("doing commit")
        git_commit(message)
        push = True
    if push:
        notify("doing push")
        git_push()

def print_file(filename):
    run_program(["lp", filename])

def run_program(command):
    try:
        cp = run(command, capture_output=True, text=True, check=True)
    except CalledProcessError as exc:
       #if exc.stdout:
       #    print("stdout:", exc.stdout)
        if exc.stderr:
            raise ValueError(exc.stderr)
        raise ValueError(f"{command} failed with {exc.returncode}")
    return cp.stderr + cp.stdout



if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", "-s", action="store_true", default=False)
    parser.add_argument("--commit", "-c", metavar="COMMIT-MESSAGE")
    parser.add_argument("--push", "-p", action="store_true", default=False)
    parser.add_argument("--commit-push", "-C", metavar="COMMIT-MESSAGE")
    parser.add_argument("--print", "-T", metavar="FILENAME")
    parser.add_argument("--test", "-t", default=(), metavar="COMMAND-ARG", nargs="+")
    args = parser.parse_args()

    if args.status:
        print("status:", git_status())
    elif args.commit:
        print("commit:", args.commit)
        git_commit(args.commit)
    elif args.push:
        git_push()
    elif args.commit_push:
        print("commit_push:", args.commit_push)
        git_commit_push(args.commit_push)
    elif args.print:
        print("print:", args.print)
        print_file(args.print)
    elif args.test:
        command = args.test
        print("run:", command)
        stdout = run_program(command)
        print(stdout)
