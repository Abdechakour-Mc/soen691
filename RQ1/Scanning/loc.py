import os
import csv
from tqdm import tqdm  # For progress indication

# Constants
AVERAGE_CHARS_PER_LINE = 40  # Average characters per line in JavaScript
CSV_FILE = './loc_reports/pre2019_repos_loc.csv'  # Output CSV file name

def count_characters(file_path):
    """Count the total number of characters in a file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return sum(len(line) for line in file)
    except UnicodeDecodeError:
        # Fallback to 'latin-1' if 'utf-8' fails
        with open(file_path, 'r', encoding='latin-1') as file:
            return sum(len(line) for line in file)

def count_characters_in_repo(repo_path):
    """Count the total number of characters in JavaScript files in a repository."""
    total_chars = 0
    # Use tqdm to show progress for files in the repository
    for root, _, files in tqdm(os.walk(repo_path), desc=f"Processing {os.path.basename(repo_path)}", unit="files"):
        for file in files:
            if file.endswith('.js'):
                file_path = os.path.join(root, file)
                total_chars += count_characters(file_path)
    return total_chars

def calculate_estimated_loc(total_chars):
    """Calculate the estimated LOC using the formula and round it to the nearest integer."""
    return round(total_chars / AVERAGE_CHARS_PER_LINE)

def main():
    repos_folder = '../Data Collection/repos/pre-repos'  # Path to the folder containing all projects
    results = []

    # Iterate through each repository with progress indication
    for repo_name in tqdm(os.listdir(repos_folder), desc="Processing Repositories", unit="repo"):
        repo_path = os.path.join(repos_folder, repo_name)
        if os.path.isdir(repo_path):
            total_chars = count_characters_in_repo(repo_path)
            estimated_loc = calculate_estimated_loc(total_chars)
            results.append([repo_name, estimated_loc])

    # Ensure the output directory exists
    os.makedirs(os.path.dirname(CSV_FILE), exist_ok=True)

    # Write results to a CSV file
    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        csvwriter = csv.writer(csvfile)
        # Write header
        csvwriter.writerow(['Repository', 'Estimated LOC (JavaScript)'])
        # Write data rows
        csvwriter.writerows(results)

    print(f"Results exported to {CSV_FILE}")

if __name__ == "__main__":
    main()