import csv
import requests
import time
import os
from urllib.parse import urlparse

def parse_github_url(html_url):
    """Extract owner and repo name from a GitHub URL"""
    parsed_url = urlparse(html_url)
    path_parts = parsed_url.path.strip('/').split('/')
    
    if len(path_parts) < 2 or parsed_url.netloc != 'github.com':
        return None, None
    
    return path_parts[0], path_parts[1]

def get_repo_contributors_count_graphql(owner, repo, token):
    """
    Get the number of contributors for a GitHub repository using GraphQL API
    
    Args:
        owner: Repository owner/organization
        repo: Repository name
        token: GitHub personal access token
    
    Returns:
        int: The number of contributors
    """
    graphql_url = 'https://api.github.com/graphql'
    
    # GraphQL query to get repository's contributors
    query = """
    query($owner: String!, $repo: String!) {
      repository(owner: $owner, name: $repo) {
        mentionableUsers(first: 1) {
          totalCount
        }
      }
    }
    """
    
    variables = {
        "owner": owner,
        "repo": repo
    }
    
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    
    try:
        response = requests.post(
            graphql_url,
            headers=headers,
            json={'query': query, 'variables': variables}
        )
        
        if response.status_code == 200:
            result = response.json()
            if 'errors' in result:
                print(f"GraphQL Error for {owner}/{repo}: {result['errors']}")
                return get_repo_contributors_count_rest(owner, repo, token)  # Fallback to REST API
            
            data = result.get('data', {})
            repo_data = data.get('repository', {})
            if repo_data:
                return repo_data.get('mentionableUsers', {}).get('totalCount', 0)
            else:
                print(f"Repository {owner}/{repo} not found or not accessible")
                return 0
        else:
            print(f"Failed GraphQL request: Status code {response.status_code}")
            # Fallback to REST API if GraphQL fails
            return get_repo_contributors_count_rest(owner, repo, token)
            
    except Exception as e:
        print(f"Error in GraphQL query for {owner}/{repo}: {str(e)}")
        # Fallback to REST API if GraphQL fails
        return get_repo_contributors_count_rest(owner, repo, token)

def get_repo_contributors_count_rest(owner, repo, token):
    """
    Get contributors count using REST API as fallback
    
    Args:
        owner: Repository owner/organization
        repo: Repository name
        token: GitHub personal access token
    
    Returns:
        int: The number of contributors
    """
    print(f"Using REST API fallback for {owner}/{repo}")
    api_url = f"https://api.github.com/repos/{owner}/{repo}/contributors"
    headers = {
        'Authorization': f'token {token}',
        'Accept': 'application/vnd.github.v3+json'
    }
    
    try:
        # Count all contributors by paginating through results
        contributors_count = 0
        page = 1
        per_page = 100  # Maximum allowed by GitHub
        
        while True:
            response = requests.get(
                f"{api_url}?page={page}&per_page={per_page}&anon=true", 
                headers=headers
            )
            
            if response.status_code == 200:
                contributors = response.json()
                if not contributors:
                    break
                    
                contributors_count += len(contributors)
                if len(contributors) < per_page:
                    break
                    
                page += 1
            else:
                print(f"REST API error: Status code {response.status_code}")
                break
            
            # Respect rate limits
            if 'X-RateLimit-Remaining' in response.headers and int(response.headers['X-RateLimit-Remaining']) < 5:
                reset_time = int(response.headers['X-RateLimit-Reset'])
                wait_time = max(0, reset_time - time.time()) + 1
                print(f"Low rate limit. Waiting for {wait_time:.1f} seconds...")
                time.sleep(wait_time)
                
        return contributors_count
            
    except Exception as e:
        print(f"Error in REST API for {owner}/{repo}: {str(e)}")
        return 0

def process_csv_with_specific_columns(csv_path, url_column='html_url', token=None):
    """
    Process a CSV file, get contributor counts, and extract specific columns
    
    Args:
        csv_path: Path to the CSV file
        url_column: Name of the column containing the GitHub URLs
        token: GitHub personal access token
    
    Returns:
        list: List of dictionaries with only the specified columns
    """
    if not token:
        token = os.environ.get('GITHUB_TOKEN')
        if not token:
            print("Warning: No GitHub token provided. Using unauthenticated requests.")
            print("Set your token using the GITHUB_TOKEN environment variable or pass it as a parameter.")
    
    # Define required columns
    required_columns = [url_column, 'stargazers_count', 'forks_count', 'open_issues_count']
    output_columns = required_columns + ['contributors_count']
    
    processed_rows = []
    
    try:
        # Read the CSV and process each row
        with open(csv_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            
            # Check if the required columns exist
            for column in required_columns:
                if column not in csv_reader.fieldnames:
                    print(f"Warning: '{column}' not found in the input CSV")
            
            # Process each row
            for row in csv_reader:
                # Create a new row with only the columns we want
                new_row = {col: row.get(col, '') for col in required_columns if col in csv_reader.fieldnames}
                
                html_url = row.get(url_column, '').strip()
                if html_url and 'github.com' in html_url:
                    owner, repo = parse_github_url(html_url)
                    if owner and repo:
                        print(f"Processing repository: {owner}/{repo}")
                        
                        # Get contributor count using GraphQL API with REST fallback
                        count = get_repo_contributors_count_graphql(owner, repo, token)
                        new_row['contributors_count'] = count
                        print(f"Repository: {html_url} | Contributors: {count}")
                        
                        # Respect GitHub API rate limits with a small delay
                        time.sleep(0.5)
                    else:
                        print(f"Skipping invalid GitHub URL: {html_url}")
                        new_row['contributors_count'] = 0
                else:
                    new_row['contributors_count'] = 0
                
                processed_rows.append(new_row)
        
        return processed_rows, output_columns
    
    except Exception as e:
        print(f"Error processing CSV file: {str(e)}")
        return [], []

def save_results_to_csv(rows, columns, output_path):
    """Save processed data to a new CSV file with only specific columns"""
    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=columns)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Results saved to {output_path}")
        return True
    except Exception as e:
        print(f"Error saving results to CSV: {str(e)}")
        return False

if __name__ == "__main__":
    # Example usage
    input_csv = "../Filtering/filtered data/pre_2021.csv"  # Replace with your CSV file path
    output_csv = "proj_meta/pre.csv"
    url_column = "html_url"  # The column containing GitHub repository URLs
    
    # Get GitHub token from environment variable or input
    github_token = os.environ.get('GITHUB_TOKEN')
    if not github_token:
        github_token = input("Enter your GitHub personal access token (or set GITHUB_TOKEN environment variable): ")
    
    # Process CSV and extract only the specific columns
    processed_rows, output_columns = process_csv_with_specific_columns(input_csv, url_column, token=github_token)
    
    if processed_rows:
        # Save results with only the specified columns
        save_results_to_csv(processed_rows, output_columns, output_csv)
        
        # Print summary
        print("\nSummary:")
        print(f"Processed {len(processed_rows)} repositories")
        
        # Calculate total contributors
        total_contributors = 0
        for row in processed_rows:
            contributors = row.get('contributors_count', 0)
            # Handle the value regardless of whether it's an integer or string
            if isinstance(contributors, int):
                total_contributors += contributors
            elif isinstance(contributors, str) and contributors.isdigit():
                total_contributors += int(contributors)
        
        print(f"Total contributors across all repositories: {total_contributors}")
    else:
        print("No data processed. Check for errors above.")