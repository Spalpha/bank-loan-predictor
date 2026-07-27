#!/usr/bin/env python3
"""
Rewrite git history: replace author and committer email OLD_EMAIL with NEW_EMAIL
on every commit in the current repository.

Usage:
  # Edit OLD_EMAIL / NEW_EMAIL or pass via arguments:
  python git-history-fixer.py --old-email x@old.com --new-email y@new.com -y
  
  # Or use interactive mode if arguments are omitted.
  python git-history-fixer.py
  
  # To rewrite only the last N commits:
  python git-history-fixer.py --old-email x@old.com --new-email y@new.com --commits 5 -y
  
  # To rewrite a specific commit ID:
  python git-history-fixer.py --old-email x@old.com --new-email y@new.com --commit-id 1a2b3c4 -y
  
After rewriting, push with:
  git push --force-with-lease
"""

import os
import sys
import subprocess
import argparse
import textwrap


def run_command(cmd, check=False):
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}", file=sys.stderr)
        print(result.stderr, file=sys.stderr)
        sys.exit(result.returncode)
    return result.stdout.strip(), result.returncode


def main():
    parser = argparse.ArgumentParser(
        description="Rewrite git history to replace author and committer email.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(__doc__)
    )
    parser.add_argument("--old-email", help="The old incorrect email to replace")
    parser.add_argument("--new-email", help="The new correct email")
    parser.add_argument("--author-name", help="The new correct author name")
    parser.add_argument("--commits", type=int, help="Rewrite only the last N commits")
    parser.add_argument("--commit-id", help="Rewrite a specific commit hash")
    parser.add_argument("--all-branches", action="store_true", help="Rewrite history across all local branches")
    parser.add_argument("-y", "--yes", "--noconfirm", action="store_true", dest="confirm", help="Skip the confirmation prompt and proceed immediately")
    args = parser.parse_args()

    # Check if inside a git repository
    is_git_repo, returncode = run_command("git rev-parse --is-inside-work-tree")
    if returncode != 0 or is_git_repo != "true":
        print("Error: Not inside a git repository. Please navigate to the correct directory.", file=sys.stderr)
        sys.exit(1)

    # Detect current git email configuration
    current_git_email, _ = run_command("git config --global user.email")
    current_git_name, _ = run_command("git config --global user.name")
    
    old_email = args.old_email
    new_email = args.new_email
    new_name = args.author_name if args.author_name else ""

    interactive = not (old_email and new_email)

    if not old_email:
        old_email = input("Enter the OLD email to replace: ").strip()
        
    if not new_email:
        prompt_str = f"Enter the NEW email (press Enter to use '{current_git_email}'): " if current_git_email else "Enter the NEW email: "
        new_email = input(prompt_str).strip()
        if not new_email and current_git_email:
            new_email = current_git_email

    if interactive and not new_name:
        prompt_str = f"Enter the NEW author name (press Enter to use '{current_git_name}'): " if current_git_name else "Enter the NEW author name (Optional): "
        new_name = input(prompt_str).strip()
        if not new_name and current_git_name:
            new_name = current_git_name

    if not old_email or not new_email:
        print("Error: Both old and new emails must be provided.", file=sys.stderr)
        sys.exit(1)

    if old_email == new_email:
        print(f"Error: OLD_EMAIL and NEW_EMAIL are the same ({old_email}).", file=sys.stderr)
        sys.exit(1)

    if "@" not in old_email or "@" not in new_email:
        print("Error: Invalid email format.", file=sys.stderr)
        sys.exit(1)

    bad_branches = []
    branches_out, _ = run_command("git branch --format='%(refname:short)'")
    for branch in branches_out.splitlines():
        branch = branch.strip().replace("'", "").replace('"', '')
        if branch:
            out, _ = run_command(f'git log {branch} --author="{old_email}" -1 --format="%H"')
            if out.strip():
                bad_branches.append(branch)

    print(f"\nSummary of changes:")
    print(f"  Old Email   : {old_email}")
    print(f"  New Email   : {new_email}")
    if new_name:
        print(f"  New Name    : {new_name}")
        
    if args.all_branches:
        print(f"  Target      : ALL local branches")
        print(f"  Found       : {len(bad_branches)} branch(es) containing commits by this author:")
        if bad_branches:
            for b in bad_branches:
                print(f"                - {b}")
    elif args.commit_id:
        print(f"  Target      : Commit ID {args.commit_id} (current branch)")
    elif args.commits:
        print(f"  Target      : Last {args.commits} commits (current branch)")
    else:
        print(f"  Target      : All commits in the current branch")
        print(f"  Note        : Found {len(bad_branches)} branch(es) overall with this author's commits.")
        if len(bad_branches) > 1:
            print(f"                (Use --all-branches flag to automatically fix all of them at once)")

    if not args.confirm:
        choice = input("\nAre you sure you want to rewrite history? [y/N]: ").strip().lower()
        if choice not in ('y', 'yes'):
            print("Operation cancelled. No changes were made.")
            sys.exit(0)

    status, _ = run_command("git status --porcelain")
    if status:
        print("Error: Working tree is not clean. Please commit or stash your changes first.", file=sys.stderr)
        sys.exit(1)

    target_hashes = set()
    if args.commit_id:
        full_hash, rc = run_command(f"git rev-parse {args.commit_id}")
        if rc != 0:
            print(f"Error: Commit '{args.commit_id}' not found in this repository.", file=sys.stderr)
            sys.exit(1)
        target_hashes.add(full_hash.strip().lower())
        print(f"Targeting specific commit: {full_hash.strip()}")
    elif args.commits:
        hashes_str, _ = run_command(f"git log -n {args.commits} --format=%H")
        for h in hashes_str.splitlines():
            target_hashes.add(h.strip().lower())
        print(f"Targeting the last {args.commits} commits.")
    else:
        print("Targeting all commits in the repository.")

    print("Rewriting repository history using git rebase. This may take a while...\n")
    
    # Python script to be executed by git rebase --exec
    # It checks the author email and only amends if it matches
    exec_script = "update_author.py"
    with open(exec_script, "w") as f:
        f.write(f"""import os, subprocess, sys
result = subprocess.run(['git', 'log', '-1', '--format=%ae|%ad|%cd', '--date=iso-strict'], capture_output=True, text=True)
parts = result.stdout.strip().split('|')
if len(parts) == 3 and parts[0] == '{old_email}':
    env = os.environ.copy()
    env['GIT_AUTHOR_EMAIL'] = '{new_email}'
    env['GIT_AUTHOR_DATE'] = parts[1]
    if '{new_name}':
        env['GIT_AUTHOR_NAME'] = '{new_name}'
    env['GIT_COMMITTER_EMAIL'] = '{new_email}'
    env['GIT_COMMITTER_DATE'] = parts[2]
    if '{new_name}':
        env['GIT_COMMITTER_NAME'] = '{new_name}'
    res = subprocess.run(['git', 'commit', '--amend', '--no-edit', '--reset-author', '--allow-empty'], env=env)
    sys.exit(res.returncode)
""")

    branches_to_process = bad_branches if args.all_branches else ["HEAD"]
    current_branch, _ = run_command("git branch --show-current")
    
    if args.all_branches and not bad_branches:
        print("No branches require fixing. Exiting.")
        sys.exit(0)

    for branch in branches_to_process:
        if branch != "HEAD":
            print(f"\n--- Processing branch: {branch} ---")
            run_command(f"git checkout {branch}")
            
        root_hash = ""
        if args.commit_id and not args.all_branches:
            base_commit = f"{args.commit_id}^"
            rebase_target = base_commit
        elif args.commits and not args.all_branches:
            base_commit = f"HEAD~{args.commits}"
            rebase_target = base_commit
        else:
            # Get up to the 50th first-parent commit safely
            hashes_out, _ = run_command("git rev-list --first-parent --max-count=51 HEAD")
            hashes = hashes_out.strip().splitlines()
            if len(hashes) <= 50:
                root_hash = hashes[-1]
                rebase_target = "--root"
                print("Rewriting from root commit to preserve merge history safely.")
            else:
                base_commit = hashes[-1]
                rebase_target = base_commit
                print("Rewriting the last 50 commits to preserve merge history safely.")

        # Run the rebase
        script_path = os.path.abspath(exec_script).replace('\\', '/')
        cmd = f'git rebase --committer-date-is-author-date --exec "python {script_path}" {rebase_target}'
        os.system(cmd)
        
        print(f"\nDone with branch '{branch}'.")
        print(f"Pushing branch '{branch}' to GitHub...")
        push_ref = branch if branch != "HEAD" else "HEAD"
        _, rc = run_command(f"git push --force origin {push_ref}")
        if rc == 0:
            print(f"Successfully pushed {push_ref} to GitHub!")
        else:
            print(f"Could not automatically push {push_ref} to GitHub. You may need to run this manually:")
            print(f"  git push --force origin {push_ref}")

    if args.all_branches and current_branch:
        print(f"\nReturning to original branch: {current_branch}")
        run_command(f"git checkout {current_branch}")

    if os.path.exists(exec_script):
        os.remove(exec_script)

    print(f"\nAll operations completed. Occurrences of '{old_email}' were rewritten to '{new_email}'.")

if __name__ == "__main__":
    main()
