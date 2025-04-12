import os
from datetime import datetime, timezone
from github import Github
import csv
import pandas as pd
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class IssueResolutionAnalyzer:
    def __init__(self, github_token=None):
        """
        Initialize with GitHub token (from env if not provided)
        """
        self.github_token = github_token or os.getenv('GITHUB_TOKEN',)
        if not self.github_token:
            raise ValueError("GitHub token is required")
        self.github = Github(self.github_token)

    def get_repo_issues(self, repo_url, max_issues=100, cutoff_date=datetime(2023, 1, 1, tzinfo=timezone.utc)):
        """
        Fetch closed issues with both created and closed dates
        
        Args:
            repo_url (str): GitHub repository URL
            max_issues (int, optional): Maximum number of issues to fetch. Defaults to 100.
            cutoff_date (datetime, optional): Only include issues closed before this date. 
                                              Defaults to January 1, 2023.
        
        Returns:
            list: List of dictionaries with issue data
        """
        try:
            # Extract owner/repo from URL
            parts = [p for p in repo_url.strip('/').split('/') if p]
            if len(parts) < 2:
                raise ValueError(f"Invalid GitHub URL: {repo_url}")
            repo_name = f"{parts[-2]}/{parts[-1]}"
            
            repo = self.github.get_repo(repo_name)
            # issues = repo.get_issues(state='closed', sort='updated', direction='desc')[:max_issues]
            issues = repo.get_issues(state='closed', sort='updated', direction='desc')
            
            resolution_data = []
            for issue in issues:
                # Check if issue is closed before the cutoff date
                if (issue.closed_at and 
                    issue.closed_at <= cutoff_date):
                    
                    # Calculate resolution time
                    resolution_time = (issue.closed_at - issue.created_at).total_seconds()
                    
                    resolution_data.append({
                        'repository': repo_name,
                        'issue_number': issue.number,
                        'title': issue.title,
                        'created_at': issue.created_at.isoformat(),
                        'closed_at': issue.closed_at.isoformat(),
                        'resolution_seconds': resolution_time,
                        'resolution_days': round(resolution_time / (24 * 3600), 2)
                    })
                
                # Optional: Break if we've reached max_issues
                # if len(resolution_data) >= max_issues:
                #     break
            
            return resolution_data
        except Exception as e:
            print(f"Error processing {repo_url}: {str(e)}")
            return []

    def analyze_repositories(self, input_csv, output_file='time_to_fix_summary.csv', cutoff_date=datetime(2023, 1, 1, tzinfo=timezone.utc)):
        """
        Analyze multiple repositories from CSV and save results to CSV
        
        Args:
            input_csv (str): Path to input CSV with repository URLs
            output_file (str, optional): Path to output summary CSV. Defaults to 'time_to_fix_summary.csv'.
            cutoff_date (datetime, optional): Cutoff date for issue analysis. Defaults to January 1, 2023.
        """
        # Read repository URLs from input CSV
        try:
            repo_df = pd.read_csv(input_csv)
            if 'html_url' not in repo_df.columns:
                raise ValueError("Input CSV must contain 'html_url' column")
            
            repo_urls = repo_df['html_url'].dropna().unique().tolist()
            print(f"Found {len(repo_urls)} repositories to analyze")
        except Exception as e:
            print(f"Error reading repository list: {str(e)}")
            return []
        
        all_issues = []
        summary_results = []
        
        for repo_url in repo_urls:
            print(f"\nAnalyzing {repo_url}...")
            issues = self.get_repo_issues(repo_url, cutoff_date=cutoff_date)
            
            if not issues:
                print(f"No valid closed issues found for {repo_url}")
                continue
            
            # Collect all issues for combined CSV
            all_issues.extend(issues)
            
            # Calculate statistics
            resolution_times = [i['resolution_seconds'] for i in issues]
            resolution_days = [t / (24 * 3600) for t in resolution_times]
            
            # Basic stats
            count = len(resolution_times)
            total_seconds = sum(resolution_times)
            min_time = min(resolution_times) if resolution_times else 0
            
            # Percentiles (25th, 50th/median, 75th)
            sorted_times = sorted(resolution_times)
            n = len(sorted_times)
            p25 = sorted_times[int(n * 0.25)] if n > 0 else 0
            p75 = sorted_times[int(n * 0.75)] if n > 0 else 0
            
            # Standard deviation
            mean = total_seconds / count if count > 0 else 0
            variance = sum((x - mean) ** 2 for x in resolution_times) / count if count > 0 else 0
            std_dev = variance ** 0.5
            
            summary_results.append({
                'repository': issues[0]['repository'],
                'issues_analyzed': count,
                'mean_days': round(mean / (24 * 3600), 4),
                'std_dev_days': round(std_dev / (24 * 3600), 4),
                'p25_days': round(p25 / (24 * 3600), 2),
                'median_days': round(sorted_times[n//2] / (24 * 3600), 4),
                'p75_days': round(p75 / (24 * 3600), 4),
                'min_days': round(min_time / (24 * 3600), 4),
                'max_days': round(max(resolution_times) / (24 * 3600), 4) if resolution_times else 0,
                'total_days': round(total_seconds / (24 * 3600), 4),
                'fast_resolutions': len([t for t in resolution_times if t < 3600])
            })
        
        # Save all issues to a combined CSV
        self._save_to_csv(all_issues, 'pre_all_repos_issues_details.csv')
        
        # Save summary results
        self._save_to_csv(summary_results, output_file)
        print(f"\nSummary results saved to {output_file}")
        
        return summary_results

    def _save_to_csv(self, data, filename):
        """Helper method to save data to CSV with UTF-8 encoding"""
        if not data:
            return
        
        keys = data[0].keys()
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(data)

if __name__ == "__main__":
    # Configuration
    INPUT_CSV = "../Data Collection/spider_output/javascript_projects_jan2018_active2021.csv"
    OUTPUT_FILE = "pre_time_to_fix_summary.csv"
    
    # Run analysis with cutoff date
    cutoff_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
    analyzer = IssueResolutionAnalyzer()
    results = analyzer.analyze_repositories(INPUT_CSV, OUTPUT_FILE, cutoff_date=cutoff_date)
    
    # Print summary
    if results:
        print("\nTime-to-Fix Statistical Summary (in days):")
        print("=" * 85)
        print("{:<30} | {:>6} | {:>6} | {:>6} | {:>6} | {:>6} | {:>6} | {:>6} | {:>6}".format(
            "Repository", "Count", "Mean", "Median", "P25", "P75", "Min", "Max", "<1h"))
        print("-" * 85)

        for repo in results:
            print("{:<30} | {:>6} | {:>6.1f} | {:>6.1f} | {:>6.1f} | {:>6.1f} | {:>6.1f} | {:>6.1f} | {:>6}".format(
                repo['repository'],
                repo['issues_analyzed'],
                repo['mean_days'],
                repo['median_days'],
                repo['p25_days'],
                repo['p75_days'],
                repo['min_days'],
                repo['max_days'],
                repo['fast_resolutions']))
    else:
        print("\nNo results to display")