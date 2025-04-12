import os
import re
from typing import List, Dict, Any
import urllib.parse
import pandas as pd
from datetime import datetime, timezone
from dotenv import load_dotenv
from github import Github

# Load environment variables
load_dotenv()

class JavaScriptIssueCategorizer:
    # Predefined issue categories with representative keywords
    ISSUE_CATEGORIES = {
        'Runtime Errors': [
            'undefined', 'null', 'type error', 'reference error', 
            'syntax error', 'runtime exception'
        ],
        'Performance Issues': [
            'memory leak', 'performance', 'slow', 'cpu usage', 
            'rendering', 'optimization'
        ],
        'Async Programming': [
            'promise', 'async', 'callback', 'race condition', 
            'await', 'event loop'
        ],
        'State Management': [
            'state', 'props', 'redux', 'context', 'vuex', 
            'mobx', 'store', 'mutation'
        ],
        'Browser Compatibility': [
            'cross-browser', 'browser', 'dom', 'safari', 
            'chrome', 'firefox', 'ie', 'edge'
        ],
        'Security Vulnerabilities': [
            'xss', 'csrf', 'injection', 'security', 'vulnerability', 
            'authentication'
        ],
        'Dependency Management': [
            'npm', 'package', 'dependency', 'version', 
            'install', 'conflict'
        ],
        'Framework-Specific': [
            'react', 'vue', 'angular', 'svelte', 'framework', 
            'component'
        ],
        'Network & API': [
            'fetch', 'axios', 'api', 'http', 'request', 
            'response', 'timeout'
        ],
        'Configuration & Build': [
            'webpack', 'babel', 'config', 'build', 'compile', 
            'transpile', 'setup'
        ]
    }

    def __init__(self, github_token: str = None):
        """
        Initialize the GitHub Issue Categorizer
        """
        self.github_token = github_token or os.getenv('GITHUB_TOKEN')
        if not self.github_token:
            raise ValueError("GitHub token is required")
        
        self.github_client = Github(self.github_token)

    def parse_github_url(self, url: str) -> str:
        """Parse GitHub URL to extract owner and repository name with better error handling"""
        try:
            parsed_url = urllib.parse.urlparse(url)
            path_parts = parsed_url.path.strip('/').split('/')
            
            if len(path_parts) < 2:
                # Try alternative formats
                if 'github.com' in url:
                    # Handle cases like 'github.com/owner/repo'
                    url_parts = url.split('github.com/')[-1].split('/')
                    if len(url_parts) >= 2:
                        return f"{url_parts[0]}/{url_parts[1]}"
                
                raise ValueError(f"URL doesn't contain both owner and repo: {url}")
            
            return f"{path_parts[0]}/{path_parts[1]}"
        except Exception as e:
            raise ValueError(f"Failed to parse GitHub URL {url}: {str(e)}")

    def fetch_repository_issues(self, repo_url: str, max_issues: int = 500, 
                                 start_date: datetime = None, 
                                 end_date: datetime = None) -> List[Dict[str, Any]]:
        """
        Fetch issues from a GitHub repository with date filtering and progress tracking
        
        Args:
            repo_url (str): URL of the GitHub repository
            max_issues (int): Maximum number of issues to fetch
            start_date (datetime, optional): Earliest issue creation date to include
            end_date (datetime, optional): Latest issue creation date to include
        """
        print(f"\nFetching issues for repository: {repo_url}")
        try:
            repo_path = self.parse_github_url(repo_url)
            print(f"Parsed repository path: {repo_path}")
            
            repository = self.github_client.get_repo(repo_path)
            total_issues = repository.get_issues(state='all').totalCount
            print(f"Found {total_issues} total issues (will fetch up to {max_issues})")
            
            # Ensure start and end dates are timezone-aware
            if start_date and start_date.tzinfo is None:
                start_date = start_date.replace(tzinfo=timezone.utc)
            if end_date and end_date.tzinfo is None:
                end_date = end_date.replace(tzinfo=timezone.utc)
            
            issues = []
            for i, issue in enumerate(repository.get_issues(state='all')[:max_issues]):
                # Ensure issue creation time is timezone-aware
                issue_created_at = issue.created_at
                if issue_created_at.tzinfo is None:
                    issue_created_at = issue_created_at.replace(tzinfo=timezone.utc)
                
                # Date filtering with timezone-aware comparison
                if start_date and issue_created_at < start_date:
                    continue
                if end_date and issue_created_at > end_date:
                    continue
                
                if (i + 1) % 50 == 0:
                    print(f"Processed {i + 1} issues...")
                
                issues.append({
                    'title': issue.title,
                    'body': issue.body or '',
                    'state': issue.state,
                    'created_at': issue_created_at,
                })
            
            print(f"Successfully fetched {len(issues)} issues within the specified date range")
            return issues
        except Exception as e:
            print(f"Error fetching issues for {repo_url}: {str(e)}")
            return []

    def categorize_issue(self, issue_text: str) -> Dict[str, float]:
        """
        Categorize an issue based on predefined categories
        
        Returns a dictionary of category scores
        """
        # Lowercase and prepare text
        text = issue_text.lower()
        
        # Calculate category scores
        category_scores = {}
        for category, keywords in self.ISSUE_CATEGORIES.items():
            # Count keyword matches
            matches = sum(keyword in text for keyword in keywords)
            category_scores[category] = matches
        
        return category_scores

    def analyze_repository_issues(self, repo_url: str, 
                                  start_date: datetime = None, 
                                  end_date: datetime = None) -> Dict[str, Any]:
        """
        Comprehensive analysis of repository issues with date filtering
        """
        print(f"\nStarting analysis for repository: {repo_url}")
        
        # Fetch issues with date filtering
        issues = self.fetch_repository_issues(repo_url, 
                                              start_date=start_date, 
                                              end_date=end_date)
        if not issues:
            return {'error': 'No issues fetched'}
        
        print("Categorizing issues...")
        
        # Aggregate category scores
        category_totals = {
            category: 0 for category in self.ISSUE_CATEGORIES.keys()
        }
        
        # Categorize each issue
        for i, issue in enumerate(issues):
            if (i + 1) % 100 == 0:
                print(f"Categorized {i + 1}/{len(issues)} issues")
                
            # Combine title and body for comprehensive analysis
            full_text = f"{issue['title']} {issue['body']}"
            category_scores = self.categorize_issue(full_text)
            
            # Accumulate scores
            for category, score in category_scores.items():
                category_totals[category] += score
        
        # Calculate percentages
        total_matches = sum(category_totals.values())
        category_percentages = {
            category: (count / total_matches * 100) if total_matches > 0 else 0
            for category, count in category_totals.items()
        }
        
        print(f"Completed analysis for {repo_url}")
        
        # Additional repository-level insights
        return {
            'total_issues': len(issues),
            'category_distribution': category_percentages,
            'most_common_categories': sorted(
                category_percentages.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:3]
        }

    def analyze_multiple_repositories(self, input_csv: str = "./repos.csv", 
                                      start_date: datetime = None, 
                                      end_date: datetime = None) -> pd.DataFrame:
        """
        Analyze multiple repositories from a CSV file with date filtering
        
        Args:
            input_csv: Path to CSV file containing repository URLs (must have 'html_url' column)
            start_date: Earliest issue creation date to include
            end_date: Latest issue creation date to include
        """
        # Read repository URLs from CSV
        try:
            repos_df = pd.read_csv(input_csv)
            if 'html_url' not in repos_df.columns:
                raise ValueError("CSV file must contain an 'html_url' column")
            
            repo_urls = repos_df['html_url'].dropna().unique().tolist()
            print(f"\nFound {len(repo_urls)} repositories to analyze in {input_csv}")
        except Exception as e:
            print(f"Error reading repository list from {input_csv}: {str(e)}")
            return pd.DataFrame()
        
        print(f"\nStarting analysis for {len(repo_urls)} repositories")
        results = []
        
        for i, repo_url in enumerate(repo_urls, 1):
            print(f"\nProcessing repository {i}/{len(repo_urls)}: {repo_url}")
            try:
                # Analyze repository with date filtering
                analysis = self.analyze_repository_issues(
                    repo_url, 
                    start_date=start_date, 
                    end_date=end_date
                )
                
                if 'error' in analysis:
                    print(f"Skipping {repo_url} due to error: {analysis['error']}")
                    continue
                
                # Prepare row for CSV
                row = {
                    'Repository': repo_url,
                    'Total Issues': analysis['total_issues'],
                }
                
                # Add category percentages
                for category, percentage in analysis['category_distribution'].items():
                    row[f'{category} %'] = round(percentage, 2)
                
                # Add top 3 categories
                top_categories = [cat for cat, _ in analysis['most_common_categories']]
                row['Top Categories'] = ', '.join(top_categories)
                
                results.append(row)
            
            except Exception as e:
                print(f"Error analyzing {repo_url}: {str(e)}")
        
        print("\nAnalysis completed for all repositories")
        return pd.DataFrame(results)

def main():
    # Initialize categorizer
    categorizer = JavaScriptIssueCategorizer()
    
    # Define date range with timezone
    start_date = datetime(2018, 1, 1, tzinfo=timezone.utc)
    end_date = datetime(2021, 1, 1, tzinfo=timezone.utc)
    
    # Perform analysis from CSV file with date filtering
    results_df = categorizer.analyze_multiple_repositories(
        "../Data Collection/spider_output/javascript_projects_jan2022_active2025.csv",
        start_date=start_date,
        end_date=end_date
    )
    
    if not results_df.empty:
        # Export to CSV
        output_file = "data/javascript_repository_issues_2018_2021.csv"
        results_df.to_csv(output_file, index=False)
        print(f"\nFinal results saved to {output_file}")
    else:
        print("\nNo results to save due to errors")

if __name__ == "__main__":
    main()