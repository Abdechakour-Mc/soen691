import os
import subprocess
import pandas as pd
import re
import time
import multiprocessing
from functools import partial
from datetime import datetime

# Directory where Git projects are stored
projects_folder = "../Data Collection/repos/post-repos"
# projects_folder = "../Data Collection/repos/pre-repos"
# projects_folder = "temp/"
# since_date = "2018-01-01"
since_date = "2022-01-01"
until_date = "2025-01-01"
TIMEOUT = 60 * 15  # 15 minutes timeout in seconds

def get_commit_frequency(project_path):
    """Calculates the average commits per day over the entire date range."""
    try:
        # Modify the command to work better with Windows
        command = ['git', 'log', f'--since={since_date}', f'--until={until_date}', 
                   '--pretty=format:%ad', '--date=short']
        
        # Get list of commit dates
        result = subprocess.run(command, cwd=project_path, capture_output=True, text=True, check=True)
        
        # Count occurrences of each date
        dates = result.stdout.strip().split('\n')
        total_commits = len([date for date in dates if date.strip() != ""])
        
        # Calculate total days in the period (inclusive)
        start = datetime.strptime(since_date, "%Y-%m-%d")
        end = datetime.strptime(until_date, "%Y-%m-%d")
        total_days = (end - start).days + 1
        
        avg_commits_per_day = total_commits / total_days if total_days > 0 else 0
        return avg_commits_per_day
    except subprocess.CalledProcessError as e:
        print(f"Error fetching commit frequency for {project_path}: {e}")
        return 0

def get_code_churn(project_path):
    """Calculates the average lines added & deleted per commit."""
    try:
        # Use array format for command to avoid shell issues
        command = ['git', 'log', '--numstat', '--pretty=format:%H', 
                   f'--since={since_date}', f'--until={until_date}']
        
        result = subprocess.run(command, cwd=project_path, capture_output=True, text=True, check=True)

        total_additions = 0
        total_deletions = 0
        total_commits = 0
        current_commit = None

        for line in result.stdout.strip().split("\n"):
            line = line.strip()

            if re.match(r"^[0-9a-f]{40}$", line):  # Detect commit hash
                current_commit = line
                total_commits += 1  # Count each commit
            elif line and current_commit:
                parts = line.split("\t")
                if len(parts) == 3:  # numstat format: added, deleted, filename
                    added = int(parts[0]) if parts[0].isdigit() else 0
                    deleted = int(parts[1]) if parts[1].isdigit() else 0
                    total_additions += added
                    total_deletions += deleted

        avg_additions = total_additions / total_commits if total_commits else 0
        avg_deletions = total_deletions / total_commits if total_commits else 0

        return avg_additions, avg_deletions
    except subprocess.CalledProcessError as e:
        print(f"Error fetching code churn for {project_path}: {e}")
        return 0, 0

def process_project(project_path, project_name):
    """Process a single project."""
    try:
        avg_commits = get_commit_frequency(project_path)
        avg_additions, avg_deletions = get_code_churn(project_path)
        
        return {
            "project": project_name,
            "avg_commits_per_day": avg_commits,
            "avg_lines_added_per_commit": avg_additions,
            "avg_lines_deleted_per_commit": avg_deletions
        }
    except Exception as e:
        print(f"Failed to process {project_name}: {e}")
        return None

def process_with_timeout(func, args=(), kwargs={}, timeout_duration=TIMEOUT):
    """Run a function with a timeout."""
    pool = multiprocessing.Pool(processes=1)
    result = pool.apply_async(func, args=args, kwds=kwargs)
    try:
        val = result.get(timeout=timeout_duration)
        pool.close()
        pool.join()
        return val
    except multiprocessing.TimeoutError:
        pool.terminate()
        pool.join()
        print(f"Function {func.__name__} timed out after {timeout_duration} seconds")
        return None

def main():
    project_data = []
    skipped_projects = []

    for project_name in os.listdir(projects_folder):
        project_path = os.path.join(projects_folder, project_name)
        if os.path.isdir(project_path) and os.path.exists(os.path.join(project_path, ".git")):
            print(f"Processing project: {project_name}")
            
            project_info = process_with_timeout(
                process_project, 
                args=(project_path, project_name)
            )
            
            if project_info:
                project_data.append(project_info)
            else:
                skipped_projects.append(project_name)
                print(f"Skipping {project_name} due to timeout or error")

    # Save results to CSV
    if project_data:
        df = pd.DataFrame(project_data)
        output_csv = "new/post_commit_analysis_summary.csv"
        df.to_csv(output_csv, index=False)
        print(f"Exported summary to {output_csv} with {len(project_data)} projects")
    else:
        print("No data was collected.")
        
    # Report on skipped projects
    if skipped_projects:
        print(f"Skipped {len(skipped_projects)} projects due to timeouts or errors:")
        for project in skipped_projects:
            print(f"  - {project}")
        
        # Save skipped projects to file
        with open("skipped_projects.txt", "w") as f:
            for project in skipped_projects:
                f.write(f"{project}\n")

if __name__ == "__main__":
    multiprocessing.freeze_support()  # For Windows compatibility
    main()



# import os
# import subprocess
# import pandas as pd
# import re
# import time
# import multiprocessing
# from functools import partial

# # Directory where Git projects are stored
# projects_folder = "../Data Collection/repos/post-repos"
# since_date = "2022-01-01"
# until_date = "2025-01-01"
# TIMEOUT = 60*15  # 1 minute timeout in seconds


# def get_commit_frequency(project_path):
#     """Calculates the average commits per day."""
#     try:
#         # Modify the command to work better with Windows
#         command = ['git', 'log', f'--since={since_date}', f'--until={until_date}', 
#                   '--pretty=format:%ad', '--date=short']
        
#         # Get list of commit dates
#         result = subprocess.run(command, cwd=project_path, capture_output=True, text=True, check=True)
        
#         # Count occurrences of each date
#         dates = result.stdout.strip().split('\n')
#         date_counts = {}
        
#         for date in dates:
#             if date:
#                 date_counts[date] = date_counts.get(date, 0) + 1
        
#         total_commits = sum(date_counts.values())
#         unique_days = len(date_counts)
        
#         avg_commits_per_day = total_commits / unique_days if unique_days else 0
#         return avg_commits_per_day
#     except subprocess.CalledProcessError as e:
#         print(f"Error fetching commit frequency for {project_path}: {e}")
#         return 0


# def get_code_churn(project_path):
#     """Calculates the average lines added & deleted per commit."""
#     try:
#         # Use array format for command to avoid shell issues
#         command = ['git', 'log', '--numstat', '--pretty=format:%H', 
#                   f'--since={since_date}', f'--until={until_date}']
        
#         result = subprocess.run(command, cwd=project_path, capture_output=True, text=True, check=True)

#         total_additions = 0
#         total_deletions = 0
#         total_commits = 0
#         current_commit = None

#         for line in result.stdout.strip().split("\n"):
#             line = line.strip()

#             if re.match(r"^[0-9a-f]{40}$", line):  # Detect commit hash
#                 current_commit = line
#                 total_commits += 1  # Count each commit
#             elif line and current_commit:
#                 parts = line.split("\t")
#                 if len(parts) == 3:  # numstat format: added, deleted, filename
#                     added = int(parts[0]) if parts[0].isdigit() else 0
#                     deleted = int(parts[1]) if parts[1].isdigit() else 0
#                     total_additions += added
#                     total_deletions += deleted

#         avg_additions = total_additions / total_commits if total_commits else 0
#         avg_deletions = total_deletions / total_commits if total_commits else 0

#         return avg_additions, avg_deletions
#     except subprocess.CalledProcessError as e:
#         print(f"Error fetching code churn for {project_path}: {e}")
#         return 0, 0


# def process_project(project_path, project_name):
#     """Process a single project."""
#     try:
#         avg_commits = get_commit_frequency(project_path)
#         avg_additions, avg_deletions = get_code_churn(project_path)
        
#         return {
#             "project": project_name,
#             "avg_commits_per_day": round(avg_commits, 2),
#             "avg_lines_added_per_commit": round(avg_additions, 2),
#             "avg_lines_deleted_per_commit": round(avg_deletions, 2)
#         }
#     except Exception as e:
#         print(f"Failed to process {project_name}: {e}")
#         return None


# def process_with_timeout(func, args=(), kwargs={}, timeout_duration=TIMEOUT):
#     """Run a function with a timeout."""
#     pool = multiprocessing.Pool(processes=1)
#     result = pool.apply_async(func, args=args, kwds=kwargs)
#     try:
#         val = result.get(timeout=timeout_duration)
#         pool.close()
#         pool.join()
#         return val
#     except multiprocessing.TimeoutError:
#         pool.terminate()
#         pool.join()
#         print(f"Function {func.__name__} timed out after {timeout_duration} seconds")
#         return None


# def main():
#     project_data = []
#     skipped_projects = []

#     for project_name in os.listdir(projects_folder):
#         project_path = os.path.join(projects_folder, project_name)
#         if os.path.isdir(project_path) and os.path.exists(os.path.join(project_path, ".git")):
#             print(f"Processing project: {project_name}")
            
#             project_info = process_with_timeout(
#                 process_project, 
#                 args=(project_path, project_name)
#             )
            
#             if project_info:
#                 project_data.append(project_info)
#             else:
#                 skipped_projects.append(project_name)
#                 print(f"Skipping {project_name} due to timeout or error")

#     # Save results to CSV
#     if project_data:
#         df = pd.DataFrame(project_data)
#         df.to_csv("post_commit_analysis_summary.csv", index=False)
#         print(f"Exported summary to commit_analysis_summary.csv with {len(project_data)} projects")
#     else:
#         print("No data was collected.")
        
#     # Report on skipped projects
#     if skipped_projects:
#         print(f"Skipped {len(skipped_projects)} projects due to timeouts or errors:")
#         for project in skipped_projects:
#             print(f"  - {project}")
        
#         # Save skipped projects to file
#         with open("skipped_projects.txt", "w") as f:
#             for project in skipped_projects:
#                 f.write(f"{project}\n")


# if __name__ == "__main__":
#     multiprocessing.freeze_support()  # For Windows compatibility
#     main()