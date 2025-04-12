#!/usr/bin/env python3

import os
import subprocess
import json
import csv
import sys
from datetime import datetime

# Configuration
PROJECTS_FOLDER = "../Data Collection/repos/post-repos"  # Directory containing your projects
OUTPUT_FILE = "owasp_reports/post2025/dependency_check_summary.csv"
DETAILED_OUTPUT_FILE = "owasp_reports/post2025/dependency_check_details.csv"
LOG_FILE = "owasp_reports/post2025/dependency_check_logs.txt"

# Path to dependency-check.bat
DEPENDENCY_CHECK = "dependency-check.bat"

def setup_logging():
    """Configure logging to file"""
    # Extract the directory path from LOG_FILE
    log_directory = os.path.dirname(LOG_FILE)
    
    # Create the directory if it doesn't exist
    if log_directory and not os.path.exists(log_directory):
        os.makedirs(log_directory)
    
    # Write to the log file
    with open(LOG_FILE, "w", encoding="utf-8") as log_file:
        log_file.write(f"OWASP Dependency-Check Scan started at {datetime.now()}\n")
        log_file.write("-" * 80 + "\n\n")

def log_message(message):
    """Log a message to both console and log file"""
    print(message)
    with open(LOG_FILE, "a", encoding="utf-8") as log_file:
        log_file.write(f"{message}\n")

def check_dependency_check_installation():
    """Check if OWASP Dependency-Check is installed and accessible"""
    try:
        process = subprocess.Popen(
            [DEPENDENCY_CHECK, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        stdout, stderr = process.communicate()
        
        if process.returncode == 0:
            log_message(f"OWASP Dependency-Check version detected")
            return True
        else:
            log_message(f"Error checking Dependency-Check installation: {stderr}")
            return False
    except FileNotFoundError:
        log_message(f"Dependency-Check not found at '{DEPENDENCY_CHECK}'. Please check the path.")
        return False

def scan_project(project_path, project_name):
    """Run OWASP Dependency-Check on a project and return the results"""
    log_message(f"\nScanning project: {project_name}")
    
    # Create output directory if it doesn't exist
    output_dir = os.path.join(project_path, "dependency-check-report")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    output_file = os.path.join(output_dir, "dependency-check-report.json")
    
    try:
        # Run the Dependency-Check scan
        process = subprocess.Popen(
            [
                DEPENDENCY_CHECK,
                "--project", project_name,
                "--scan", project_path,
                "--format", "JSON",
                "--out", output_dir,
                "--noupdate"  # Skip NVD database updates to speed up scans
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace"
        )
        
        stdout, stderr = process.communicate()
        
        if process.returncode != 0:
            log_message(f"Error scanning project {project_name}: Exit code {process.returncode}")
            log_message(f"Error details: {stderr}")
            return None
        
        # Check if the output file exists
        if not os.path.exists(output_file):
            log_message(f"Output file not found for project {project_name}")
            return None
        
        # Read and parse the JSON report
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                scan_result = json.load(f)
                return scan_result
        except json.JSONDecodeError as e:
            log_message(f"Error parsing Dependency-Check output for {project_name}: {e}")
            return None
            
    except Exception as e:
        log_message(f"Exception scanning project {project_name}: {e}")
        return None

def process_scan_results(project_name, scan_result, summary_data, detailed_data):
    """Process scan results and extract vulnerability data"""
    if not scan_result:
        # Add an entry showing the project was scanned but no results were found
        summary_data.append({
            'projectName': project_name,
            'criticalSeverityCount': 0,
            'highSeverityCount': 0,
            'mediumSeverityCount': 0,
            'lowSeverityCount': 0,
            'totalVulnerabilities': 0
        })
        return
    
    # Initialize counters
    critical_count = 0
    high_count = 0
    medium_count = 0
    low_count = 0
    total_count = 0
    
    try:
        # Extract dependencies from scan results
        dependencies = scan_result.get('dependencies', [])
        
        # Process each dependency
        for dependency in dependencies:
            # Get vulnerabilities for this dependency
            vulnerabilities = dependency.get('vulnerabilities', [])
            
            if not vulnerabilities:
                continue
                
            # Extract dependency details
            dependency_name = dependency.get('fileName', 'N/A')
            dependency_path = dependency.get('filePath', 'N/A')
            
            # Process each vulnerability
            for vuln in vulnerabilities:
                # Get severity (OWASP DC uses CVSS to determine severity)
                cvss_v3 = vuln.get('cvssv3', {})
                cvss_v2 = vuln.get('cvssv2', {})
                
                # Use CVSS v3 if available, otherwise use v2
                cvss_score = cvss_v3.get('baseScore', cvss_v2.get('score', 0))
                
                # Determine severity based on CVSS score
                severity = 'UNKNOWN'
                if cvss_score >= 9.0:
                    severity = 'CRITICAL'
                    critical_count += 1
                elif cvss_score >= 7.0:
                    severity = 'HIGH'
                    high_count += 1
                elif cvss_score >= 4.0:
                    severity = 'MEDIUM'
                    medium_count += 1
                elif cvss_score > 0:
                    severity = 'LOW'
                    low_count += 1
                
                if severity != 'UNKNOWN':
                    total_count += 1
                
                # Add to detailed report
                detailed_data.append({
                    'projectName': project_name,
                    'packageName': dependency_name,
                    'vulnerabilityId': vuln.get('name', 'N/A'),
                    'packagePath': dependency_path,
                    'severity': severity,
                    'cvssScore': cvss_score,
                    'cwe': ', '.join(vuln.get('cwes', [])),
                    'description': vuln.get('description', 'N/A'),
                    'references': ', '.join([ref.get('url', '') for ref in vuln.get('references', [])]),
                    'published': vuln.get('published', 'N/A')
                })
    
    except Exception as e:
        log_message(f"Error processing scan result for {project_name}: {e}")
    
    # Add the aggregated summary for the project
    summary_data.append({
        'projectName': project_name,
        'criticalSeverityCount': critical_count,
        'highSeverityCount': high_count,
        'mediumSeverityCount': medium_count,
        'lowSeverityCount': low_count,
        'totalVulnerabilities': total_count
    })

def write_csv_report(summary_data, detailed_data):
    """Write summary and detailed reports to CSV files"""
    # Create output directory if it doesn't exist
    output_dir = os.path.dirname(OUTPUT_FILE)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # Write summary report
    with open(OUTPUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = [
            'projectName',
            'criticalSeverityCount',
            'highSeverityCount',
            'mediumSeverityCount',
            'lowSeverityCount',
            'totalVulnerabilities'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_data)
    
    log_message(f"\nSummary report written to {OUTPUT_FILE}")
    
    # Write detailed report
    if detailed_data:
        with open(DETAILED_OUTPUT_FILE, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'projectName',
                'packageName',
                'vulnerabilityId',
                'packagePath',
                'severity',
                'cvssScore',
                'cwe',
                'description',
                'references',
                'published'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(detailed_data)
        
        log_message(f"Detailed report written to {DETAILED_OUTPUT_FILE}")

def generate_statistics(summary_data):
    """Generate and log overall statistics"""
    if not summary_data:
        log_message("\nNo vulnerability data to analyze.")
        return
    
    total_projects = len(summary_data)
    total_critical = sum(int(item['criticalSeverityCount']) for item in summary_data)
    total_high = sum(int(item['highSeverityCount']) for item in summary_data)
    total_medium = sum(int(item['mediumSeverityCount']) for item in summary_data)
    total_low = sum(int(item['lowSeverityCount']) for item in summary_data)
    total_vulnerabilities = sum(int(item['totalVulnerabilities']) for item in summary_data)
    
    # Find projects with vulnerabilities
    projects_with_vulnerabilities = sum(1 for item in summary_data if int(item['totalVulnerabilities']) > 0)
    
    # Find project with most vulnerabilities
    if projects_with_vulnerabilities > 0:
        most_vulnerable_project = max(summary_data, key=lambda x: int(x['totalVulnerabilities']))
    else:
        most_vulnerable_project = {'projectName': 'None', 'totalVulnerabilities': 0}
    
    log_message("\n--- DEPENDENCY-CHECK SCAN STATISTICS ---")
    log_message(f"Total projects scanned: {total_projects}")
    log_message(f"Projects with vulnerabilities: {projects_with_vulnerabilities}")
    log_message(f"Total vulnerabilities found: {total_vulnerabilities}")
    log_message(f"  - Critical severity: {total_critical}")
    log_message(f"  - High severity: {total_high}")
    log_message(f"  - Medium severity: {total_medium}")
    log_message(f"  - Low severity: {total_low}")
    log_message(f"Most vulnerable project: {most_vulnerable_project['projectName']} with {most_vulnerable_project['totalVulnerabilities']} vulnerabilities")

def find_projects(root_dir):
    """Find all projects in the directory"""
    projects = []
    
    if not os.path.exists(root_dir):
        log_message(f"Error: Directory {root_dir} does not exist!")
        return projects
    
    for item in os.listdir(root_dir):
        project_path = os.path.join(root_dir, item)
        
        # Check if it's a directory
        if os.path.isdir(project_path):
            projects.append((project_path, item))
            
    return projects

def main():
    # Setup logging
    setup_logging()
    log_message("Starting OWASP Dependency-Check vulnerability scan across projects")
    
    # Check Dependency-Check installation
    if not check_dependency_check_installation():
        log_message("Exiting due to OWASP Dependency-Check installation issues.")
        return 1
    
    # Get the projects directory from command line if provided
    if len(sys.argv) > 1:
        projects_folder = sys.argv[1]
    else:
        projects_folder = PROJECTS_FOLDER
    
    log_message(f"Scanning projects in directory: {projects_folder}")
    
    # Find all projects
    projects = find_projects(projects_folder)
    
    if not projects:
        log_message(f"No projects found in {projects_folder}")
        return 1
    
    log_message(f"Found {len(projects)} projects to scan")
    
    # Data storage
    summary_data = []
    detailed_data = []
    
    # Scan each project
    success_count = 0
    failure_count = 0
    
    for project_path, project_name in projects:
        try:
            # Run Dependency-Check on the project
            scan_result = scan_project(project_path, project_name)
            
            # Process results
            if scan_result is not None:
                process_scan_results(project_name, scan_result, summary_data, detailed_data)
                success_count += 1
            else:
                failure_count += 1
                # Add an entry showing the project was scanned but failed
                summary_data.append({
                    'projectName': project_name,
                    'criticalSeverityCount': 0,
                    'highSeverityCount': 0,
                    'mediumSeverityCount': 0,
                    'lowSeverityCount': 0,
                    'totalVulnerabilities': 0
                })
        except Exception as e:
            failure_count += 1
            log_message(f"Failed to scan project {project_name}: {e}")
            # Add an entry showing the project failed to scan
            summary_data.append({
                'projectName': f"{project_name} (SCAN FAILED)",
                'criticalSeverityCount': 0,
                'highSeverityCount': 0,
                'mediumSeverityCount': 0,
                'lowSeverityCount': 0,
                'totalVulnerabilities': 0
            })
    
    log_message(f"\nProjects successfully scanned: {success_count}")
    log_message(f"Projects with scan failures: {failure_count}")
    
    # Write CSV reports
    write_csv_report(summary_data, detailed_data)
    
    # Generate statistics
    generate_statistics(summary_data)
    
    log_message("\nOWASP Dependency-Check vulnerability scan completed")
    return 0

if __name__ == "__main__":
    sys.exit(main())