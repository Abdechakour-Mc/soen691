import os
import subprocess
import pandas as pd
import csv
from collections import defaultdict
import json
import re
from sonarqube import SonarQubeClient
import concurrent.futures
import time
import logging
from pathlib import Path
from dotenv import load_dotenv


output_dir = "sonar_reports/post2025"
os.makedirs(output_dir, exist_ok=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f"sonar_reports/post2025/sonar_scan_logs.txt"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

# SonarQube Configuration from environment variables
sonarqube_url = os.getenv("SONARQUBE_URL", "http://127.0.0.1:9000")
sonarqube_token = os.getenv("SONARQUBE_TOKEN", "squ_")  # Fallback for testing only
sonar_scanner_path = os.getenv("SONAR_SCANNER_PATH", r"sonar-scanner.bat")

# Initialize SonarQubeClient
sonar = SonarQubeClient(sonarqube_url=sonarqube_url, token=sonarqube_token)

# Directory where projects are stored
projects_folder = os.getenv("PROJECTS_FOLDER", "../Data Collection/repos/post-repos")

# Maximum workers for parallel processing
MAX_WORKERS = os.getenv("MAX_WORKERS", 4)  # Adjust based on your system capabilities


def scan_project(project_info):
    """Runs SonarQube scanner on a given project."""
    project_path, project_key = project_info
    
    sonar_scanner_command = [
        sonar_scanner_path,
        f"-Dsonar.projectKey={project_key}",
        f"-Dsonar.host.url={sonarqube_url}",
        f"-Dsonar.login={sonarqube_token}",
        f"-Dsonar.projectBaseDir={project_path}",
        f"-Dsonar.scm.disabled=true"
    ]

    try:
        logger.info(f"Running sonar-scanner for project: {project_key}")
        start_time = time.time()
        subprocess.run(sonar_scanner_command, check=True, capture_output=True, text=True)
        elapsed_time = time.time() - start_time
        logger.info(f"Completed scanning project {project_key} in {elapsed_time:.2f} seconds")
        return project_key, True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error scanning project {project_key}: {e}")
        logger.error(f"Stdout: {e.stdout}")
        logger.error(f"Stderr: {e.stderr}")
        return project_key, False


def export_scan_report(project_info, findings_list, lock):
    """Fetches SonarQube scan results and saves them into the findings list."""
    project_key, project_name = project_info
    
    try:
        # Add a small delay to prevent overwhelming the SonarQube server with requests
        time.sleep(1)
        issues = sonar.issues.search_issues(componentKeys=project_key)["issues"]
        
        if issues:
            with lock:
                for issue in issues:
                    issue['project'] = project_name
                    findings_list.append(issue)
            logger.info(f"Exported {len(issues)} issues for project {project_key}")
            return True
        else:
            logger.info(f"No issues found for project {project_key}")
            return False
    except Exception as e:
        logger.error(f"Error exporting report for {project_key}: {e}")
        return False


def parse_time(debt_str):
    """Convert a time string like '1h12min', '10min', or '2h' into total minutes."""
    if not debt_str:
        return 0
        
    hours = 0
    minutes = 0
    if 'h' in debt_str:
        match = re.search(r'(\d+)h', debt_str)
        if match:
            hours = int(match.group(1))
    if 'min' in debt_str:
        match = re.search(r'(\d+)min', debt_str)
        if match:
            minutes = int(match.group(1))
    return hours * 60 + minutes


def format_time(total_minutes):
    """Convert total minutes into a string format like '10h12min'."""
    if total_minutes == 0:
        return "0min"
        
    hours = total_minutes // 60
    minutes = total_minutes % 60
    
    if hours > 0 and minutes > 0:
        return f"{hours}h{minutes}min"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{minutes}min"


def summarize_results(input_file, output_file):
    """Reads all_results.csv and generates a summarized report."""
    if not os.path.exists(input_file):
        logger.error(f"Input file {input_file} not found!")
        return
        
    aggregated_data = defaultdict(lambda: defaultdict(int))

    try:
        # Use pandas for more efficient CSV processing
        df = pd.read_csv(input_file)
        
        for _, row in df.iterrows():
            project = row['project']

            # Count issues related to Clean Code Attributes
            category = row.get('cleanCodeAttributeCategory', '')
            if category == 'CONSISTENT':
                aggregated_data[project]['numberOfIssuesRelatedToConsistentCode'] += 1
            elif category == 'INTENTIONAL':
                aggregated_data[project]['numberOfIssuesRelatedToIntentionalCode'] += 1
            elif category == 'ADAPTABLE':
                aggregated_data[project]['numberOfIssuesRelatedToAdaptableCode'] += 1
            elif category == 'RESPONSIBLE':
                aggregated_data[project]['numberOfIssuesRelatedToResponsibleCode'] += 1

            # Count issue types
            issue_type = row.get('type', '')
            if issue_type == 'CODE_SMELL':
                aggregated_data[project]['numberOfCodeSmells'] += 1
            elif issue_type == 'BUG':
                aggregated_data[project]['numberOfBugs'] += 1
            elif issue_type == 'VULNERABILITY':
                aggregated_data[project]['numberOfVulnerabilities'] += 1

            # Process impacts for maintainability, reliability, and security - safely parse JSON
            impacts_str = row.get('impacts', '[]')
            try:
                impacts = json.loads(impacts_str) if isinstance(impacts_str, str) else impacts_str
            except json.JSONDecodeError:
                impacts = []
                
            for impact in impacts:
                quality = impact.get('softwareQuality', '')
                severity = impact.get('severity', '')
                if quality == 'MAINTAINABILITY':
                    aggregated_data[project]['numberOfIssuesRelatedToMaintainability'] += 1
                elif quality == 'RELIABILITY':
                    aggregated_data[project]['numberOfIssuesRelatedToReliability'] += 1
                elif quality == 'SECURITY':
                    aggregated_data[project]['numberOfIssuesRelatedToSecurity'] += 1

                # Count severity levels
                if severity == 'LOW':
                    aggregated_data[project]['numberOfIssuesWithLowSeverity'] += 1
                elif severity == 'MEDIUM':
                    aggregated_data[project]['numberOfIssuesWithMediumSeverity'] += 1
                elif severity == 'HIGH':
                    aggregated_data[project]['numberOfIssuesWithHighSeverity'] += 1

            # Sum up debt time
            debt = row.get('debt', '')
            aggregated_data[project]['totalTimeNeededToRemoveDebts'] += parse_time(debt)

        # Write summarized results to summary.csv
        fieldnames = [
            'project',
            'numberOfIssuesRelatedToConsistentCode',
            'numberOfIssuesRelatedToIntentionalCode',
            'numberOfIssuesRelatedToAdaptableCode',
            'numberOfIssuesRelatedToResponsibleCode',
            'numberOfBugs', 'numberOfVulnerabilities', 'numberOfCodeSmells',
            'numberOfIssuesRelatedToMaintainability',
            'numberOfIssuesRelatedToReliability',
            'numberOfIssuesRelatedToSecurity',
            'numberOfIssuesWithLowSeverity',
            'numberOfIssuesWithMediumSeverity',
            'numberOfIssuesWithHighSeverity',
            'totalTimeNeededToRemoveDebts'
        ]
        
        with open(output_file, 'w', newline='') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=fieldnames)
            writer.writeheader()

            for project, data in aggregated_data.items():
                row = {'project': project}
                for field in fieldnames[1:]:
                    row[field] = data.get(field, 0)

                # Format the total time needed to remove debts
                row['totalTimeNeededToRemoveDebts'] = format_time(row['totalTimeNeededToRemoveDebts'])
                writer.writerow(row)
        
        logger.info(f"Successfully wrote summary to {output_file}")
    except Exception as e:
        logger.error(f"Error summarizing results: {e}")


def main():
    from threading import Lock
    
    # Create output directory if it doesn't exist
    output_dir = Path("sonar_reports/post2025")
    output_dir.mkdir(exist_ok=True)
    
    # List to store all findings
    all_findings_list = []
    all_findings_lock = Lock()
    
    # Get list of projects to scan
   
    projects_to_scan = []
    for project_name in os.listdir(projects_folder):

        project_path = os.path.join(projects_folder, project_name)
        # print(project_path)
        if os.path.isdir(project_path):
            project_key = project_name
            projects_to_scan.append((project_path, project_key))
    
    start_time = time.time()
    logger.info(f"Starting scan of {len(projects_to_scan)} projects with {MAX_WORKERS} workers")
    
    # Step 1: Scan projects in parallel
    completed_projects = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(MAX_WORKERS)) as executor:
        futures = {executor.submit(scan_project, project_info): project_info for project_info in projects_to_scan}
        for future in concurrent.futures.as_completed(futures):
            project_key, success = future.result()
            if success:
                completed_projects.append((project_key, project_key))  # (project_key, project_name)
    
    logger.info(f"Completed scanning {len(completed_projects)} out of {len(projects_to_scan)} projects")
    
    # Step 2: Export scan reports in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=int(MAX_WORKERS)) as executor:
        futures = {executor.submit(export_scan_report, project_info, all_findings_list, all_findings_lock): project_info 
                  for project_info in completed_projects}
        for future in concurrent.futures.as_completed(futures):
            pass  # We're just waiting for all exports to complete
    
    # Step 3: Save all findings to all_results.csv
    all_findings_csv_file_path = output_dir / "all_results.csv"
    summary_csv_file_path = output_dir / "summary.csv"
    
    if all_findings_list:
        all_findings_df = pd.DataFrame(all_findings_list)
        all_findings_df.to_csv(all_findings_csv_file_path, index=False)
        logger.info(f"Exported all findings to {all_findings_csv_file_path}.")

        # Generate summary.csv
        summarize_results(all_findings_csv_file_path, summary_csv_file_path)
        logger.info(f"Exported summary to {summary_csv_file_path}.")
    else:
        logger.warning("No findings to export.")
    
    elapsed_time = time.time() - start_time
    logger.info(f"Complete process finished in {elapsed_time:.2f} seconds")


if __name__ == "__main__":
    main()