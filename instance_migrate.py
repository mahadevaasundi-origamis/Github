import subprocess
import os
import shutil
import stat


def force_remove_readonly(func, path, _):
    """Error handler for shutil.rmtree to handle read-only files on Windows."""
    os.chmod(path, stat.S_IWRITE)
    func(path)


def safe_rmtree(path):
    if os.path.exists(path):
        shutil.rmtree(path, onexc=force_remove_readonly)


def get_remote_branches(remote_url):
    """Returns a set of branch names that exist on the remote destination."""
    result = subprocess.run(
        ["git", "ls-remote", "--heads", remote_url],
        capture_output=True, text=True, check=True
    )
    branches = set()
    for line in result.stdout.strip().splitlines():
        if "\t" in line:
            ref = line.split("\t")[1]
            branch = ref.replace("refs/heads/", "")
            branches.add(branch)
    return branches


def get_local_branches():
    """Returns a set of branch names in the current mirror clone."""
    result = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/heads/"],
        capture_output=True, text=True, check=True
    )
    return set(result.stdout.strip().splitlines())


def get_remote_tags(remote_url):
    """Returns a set of tag names that exist on the remote destination."""
    result = subprocess.run(
        ["git", "ls-remote", "--tags", remote_url],
        capture_output=True, text=True, check=True
    )
    tags = set()
    for line in result.stdout.strip().splitlines():
        if "\t" in line:
            ref = line.split("\t")[1]
            # Skip peeled tag refs (ending with ^{})
            if not ref.endswith("^{}"):
                tag = ref.replace("refs/tags/", "")
                tags.add(tag)
    return tags


def get_local_tags():
    """Returns a set of tag names in the current mirror clone."""
    result = subprocess.run(
        ["git", "for-each-ref", "--format=%(refname:short)", "refs/tags/"],
        capture_output=True, text=True, check=True
    )
    return set(result.stdout.strip().splitlines())


def migrate_repo(source_url, dest_url, temp_dir="temp_migration"):
    """
    Clones a repo from source with --mirror and pushes only NEW branches + tags
    to destination. Skips branches and tags that already exist on the destination.
    """
    abs_temp_dir = os.path.abspath(temp_dir)
    original_dir = os.getcwd()

    try:
        # 1. Clean up any existing temp directory
        safe_rmtree(abs_temp_dir)

        print(f"--- Starting migration for: {source_url} ---")

        # 2. Mirror clone from source
        print("\nCloning from source...")
        subprocess.run(
            ["git", "clone", "--mirror", source_url, abs_temp_dir],
            check=True
        )

        os.chdir(abs_temp_dir)

        # 3. Fetch all standard refs explicitly
        print("Fetching all refs...")
        subprocess.run(["git", "fetch", "--all"], check=True)

        # ── BRANCHES ──────────────────────────────────────────────────────────

        print("\nChecking branches...")
        local_branches = get_local_branches()
        remote_branches = get_remote_branches(dest_url)

        new_branches = local_branches - remote_branches
        skipped_branches = local_branches & remote_branches

        if skipped_branches:
            print(f"⚠  Skipping {len(skipped_branches)} branch(es) already on destination:")
            for b in sorted(skipped_branches):
                print(f"     - {b}")

        if not new_branches:
            print("✓  No new branches to migrate.")
        else:
            print(f"\nPushing {len(new_branches)} new branch(es) to destination:")
            for branch in sorted(new_branches):
                print(f"  → {branch}")
                subprocess.run(
                    ["git", "push", dest_url,
                     f"refs/heads/{branch}:refs/heads/{branch}"],
                    check=True
                )
            print("✓  Branches pushed successfully.")

        # ── TAGS ──────────────────────────────────────────────────────────────

        print("\nChecking tags...")
        local_tags = get_local_tags()
        remote_tags = get_remote_tags(dest_url)

        new_tags = local_tags - remote_tags
        skipped_tags = local_tags & remote_tags

        if skipped_tags:
            print(f"⚠  Skipping {len(skipped_tags)} tag(s) already on destination:")
            for t in sorted(skipped_tags):
                print(f"     - {t}")

        if not new_tags:
            print("✓  No new tags to migrate.")
        else:
            print(f"\nPushing {len(new_tags)} new tag(s) to destination:")
            for tag in sorted(new_tags):
                print(f"  → {tag}")
                subprocess.run(
                    ["git", "push", dest_url,
                     f"refs/tags/{tag}:refs/tags/{tag}"],
                    check=True
                )
            print("✓  Tags pushed successfully.")

        # ── DONE ──────────────────────────────────────────────────────────────

        print("\n✓ Migration completed successfully!")

    except subprocess.CalledProcessError as e:
        print(f"\n✗ Git operation failed: {e}")

    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")

    finally:
        os.chdir(original_dir)
        safe_rmtree(abs_temp_dir)
        print("Temporary files cleaned up.")


if __name__ == "__main__":
    SOURCE = "https://github.com/OrigamisAI/DocuAgent.git"
    DESTINATION = "https://repos.nusummituat.com/data-and-ai/ai/docuagent.git"

    migrate_repo(SOURCE, DESTINATION)