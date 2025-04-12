import os
import subprocess
import datetime
import sys
from pathlib import Path

def revert_repos_to_date(repos_folder, target_date):
    # Convert target_date string to datetime object
    target_datetime = datetime.datetime.strptime(target_date, "%d-%m-%Y")
    # Format for git date filtering
    git_date_format = target_datetime.strftime("%Y-%m-%d")
    
    # Get absolute path to repos folder and root directory
    repos_path = Path(repos_folder).absolute()
    root_dir = os.getcwd()
    
    if not repos_path.exists():
        print(f"Error: The folder '{repos_folder}' does not exist.")
        sys.exit(1)
        
    # Get all subdirectories in the repos folder that are git repositories
    repos = [d for d in repos_path.iterdir() if d.is_dir() and (d / ".git").exists()]
    
    if not repos:
        print(f"No git repositories found in '{repos_folder}'.")
        sys.exit(1)
        
    print(f"Found {len(repos)} git repositories. Reverting to state before {target_date}...")
    
    # List to track failed projects
    failed_projects = []
    
    for repo_path in repos:
        repo_name = repo_path.name
        print(f"\nProcessing {repo_name}...")
        
        # Always return to the root directory before processing each repo
        os.chdir(root_dir)
        
        try:
            # Change directory to the repository
            os.chdir(repo_path)
            
            # Make sure we're on the main branch (could be master or main)
            try:
                # First try to determine the default branch
                result = subprocess.run(
                    ['git', 'symbolic-ref', 'refs/remotes/origin/HEAD'],
                    check=False,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode == 0:
                    default_branch = result.stdout.strip().split('/')[-1]
                else:
                    # Try common branch names if we can't determine automatically
                    for branch in ['main', 'master']:
                        branch_check = subprocess.run(
                            ['git', 'branch', '--list', branch],
                            check=False,
                            capture_output=True,
                            text=True
                        )
                        if branch_check.stdout.strip():
                            default_branch = branch
                            break
                    else:
                        # If we can't find main or master, use the current branch
                        current_branch = subprocess.run(
                            ['git', 'branch', '--show-current'],
                            check=True,
                            capture_output=True,
                            text=True
                        )
                        default_branch = current_branch.stdout.strip()
                
                print(f"Using branch: {default_branch}")
                
                # Checkout the default branch
                subprocess.run(['git', 'checkout', default_branch], check=False, capture_output=True)
            except Exception as e:
                print(f"Could not determine default branch: {str(e)}")
                print("Continuing with current branch...")
                
            # Find the most recent commit before the target date
            get_commit_cmd = [
                'git', 'rev-list', '-n', '1', 
                f'--before="{git_date_format} 23:59:59"', 
                '--all'
            ]
            
            result = subprocess.run(get_commit_cmd, check=True, capture_output=True, text=True)
            commit_hash = result.stdout.strip()
            
            if not commit_hash:
                print(f"No commits found before {target_date} in {repo_name}. Skipping.")
                failed_projects.append((repo_name, "No commits found before target date"))
                continue
                
            # Get commit date for information
            get_date_cmd = ['git', 'show', '-s', '--format=%ci', commit_hash]
            date_result = subprocess.run(get_date_cmd, check=True, capture_output=True, text=True)
            commit_date = date_result.stdout.strip()
            
            print(f"Found commit {commit_hash[:8]} from {commit_date}")
            
            # Reset to that commit
            reset_cmd = ['git', 'reset', '--hard', commit_hash]
            subprocess.run(reset_cmd, check=True, capture_output=True)
            
            print(f"Successfully reverted {repo_name} to state on {commit_date}")
            
        except subprocess.CalledProcessError as e:
            error_message = e.stderr.decode('utf-8', errors='replace') if e.stderr else str(e)
            print(f"Error processing {repo_name}: {error_message}")
            failed_projects.append((repo_name, error_message))
        except Exception as e:
            error_message = str(e)
            print(f"Unexpected error processing {repo_name}: {error_message}")
            failed_projects.append((repo_name, error_message))
        finally:
            # Always return to the root directory after processing each repo
            os.chdir(root_dir)
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    # Write the list of failed projects to a file
    if failed_projects:
        failed_projects_file = f"logs/failed_projects_{target_date}.log"
        with open(failed_projects_file, "w", encoding="utf-8") as f:
            f.write("Projects that failed to revert:\n")
            for project, error in failed_projects:
                f.write(f"{project}: {error}\n")
        print(f"\nList of failed projects saved to {failed_projects_file}")
    else:
        print("\nAll repositories were successfully reverted.")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python revert_repos.py <target_date>")
        print("Date format: DD-MM-YYYY (e.g., 01-01-2019)")
        sys.exit(1)
    
    target_date = sys.argv[1]
    # Simple validation of date format
    try:
        datetime.datetime.strptime(target_date, "%d-%m-%Y")
    except ValueError:
        print("Error: Date must be in DD-MM-YYYY format (e.g., 01-01-2019)")
        sys.exit(1)
    
    revert_repos_to_date("repos/post-repos", target_date)
    print("\nAll repositories have been processed.")