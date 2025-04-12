import requests
import datetime
import time
import os
import csv
from typing import List, Dict, Optional, Any
import logging
from dotenv import load_dotenv

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("logs/github_scraper.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class GitHubScraper:
    """
    A class to scrape GitHub repositories based on specific criteria.
    """
    
    BASE_URL = "https://api.github.com"
    MAX_SEARCH_RESULTS = 1000  # GitHub API limit
    
    def __init__(self, token: Optional[str] = None):
        """
        Initialize the GitHubScraper with an optional GitHub API token.
        
        Args:
            token: GitHub API token for authentication (optional but recommended)
        """
        self.token = token or os.getenv("GITHUB_TOKEN")
        self.session = requests.Session()
        
        if self.token:
            self.session.headers.update({"Authorization": f"token {self.token}"})
        
        self.session.headers.update({
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "GitHubProjectCollector"
        })
    
    def _make_request(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        """
        Make a request to the GitHub API with rate limit handling.
        
        Args:
            endpoint: API endpoint (without base URL)
            params: Query parameters
            
        Returns:
            API response as a dictionary or None if error occurs
        """
        url = f"{self.BASE_URL}/{endpoint}"
        
        try:
            while True:
                response = self.session.get(url, params=params)
                
                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 403 and 'rate limit exceeded' in response.text.lower():
                    reset_time = int(response.headers.get('X-RateLimit-Reset', 0))
                    sleep_time = max(reset_time - time.time(), 0) + 1
                    
                    logger.warning(f"Rate limit exceeded. Waiting for {sleep_time:.2f} seconds.")
                    time.sleep(sleep_time)
                elif response.status_code == 422 and 'Only the first 1000 search results are available' in response.text:
                    logger.warning("GitHub API limit reached: Only the first 1000 search results are available")
                    return None
                else:
                    logger.error(f"Request failed: {response.status_code} - {response.text}")
                    response.raise_for_status()
        except Exception as e:
            logger.error(f"Error making request: {str(e)}")
            return None
    
    def search_repositories(self, 
                           language: str, 
                           created_start: datetime.datetime,
                           created_end: datetime.datetime,
                           pushed_after: datetime.datetime,
                           page: int = 1,
                           per_page: int = 100) -> Optional[Dict[str, Any]]:
        """
        Search for repositories based on criteria.
        
        Args:
            language: Programming language
            created_start: Start date for repository creation
            created_end: End date for repository creation
            pushed_after: Only include repositories with commits after this date
            page: Page number for pagination
            per_page: Number of results per page
            
        Returns:
            Search results as a dictionary or None if error occurs
        """
        # Format dates for GitHub API
        created_start_str = created_start.strftime("%Y-%m-%d")
        created_end_str = created_end.strftime("%Y-%m-%d")
        pushed_after_str = pushed_after.strftime("%Y-%m-%d")
        
        # Construct query
        query = f"language:{language} created:{created_start_str}..{created_end_str} pushed:>={pushed_after_str}"
        
        params = {
            "q": query,
            "sort": "updated",  # Changed from stars to updated for better distribution
            "order": "desc",
            "page": page,
            "per_page": per_page
        }
        
        return self._make_request("search/repositories", params)
    
    def get_repositories_by_page_range(self, 
                            language: str, 
                            created_start: datetime.datetime,
                            created_end: datetime.datetime,
                            pushed_after: datetime.datetime,
                            start_page: int = 1,
                            end_page: int = 10,
                            per_page: int = 100) -> List[Dict[str, Any]]:
        """
        Get repositories matching the criteria from a specific range of pages.
        
        Args:
            language: Programming language
            created_start: Start date for repository creation
            created_end: End date for repository creation
            pushed_after: Only include repositories with commits after this date
            start_page: First page to fetch (inclusive)
            end_page: Last page to fetch (inclusive)
            per_page: Number of results per page
            
        Returns:
            List of repository data
        """
        all_repos = []
        max_page_reached = False
        
        for current_page in range(start_page, end_page + 1):
            logger.info(f"Fetching page {current_page}")
            
            if current_page > 10:
                logger.warning(f"Approaching GitHub's 1000 result limit (page {current_page})")
            
            results = self.search_repositories(
                language=language,
                created_start=created_start,
                created_end=created_end,
                pushed_after=pushed_after,
                page=current_page,
                per_page=per_page
            )
            
            if results is None:
                logger.warning(f"GitHub API limit reached at page {current_page}. Saving collected data so far.")
                max_page_reached = True
                break
            
            items = results.get("items", [])
            all_repos.extend(items)
            
            total_count = results.get("total_count", 0)
            logger.info(f"Found {len(items)} repositories on page {current_page}. Total count: {total_count}")
            
            if len(items) == 0:
                logger.info(f"No more results found after page {current_page}")
                break
                
            # Add a small delay to avoid hitting rate limits
            time.sleep(1)
        
        results_info = "GitHub API 1000 result limit reached. " if max_page_reached else ""
        logger.info(f"{results_info}Collected a total of {len(all_repos)} repositories")
        return all_repos
    
    def extract_repository_data(self, repo: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract relevant data from a repository.
        
        Args:
            repo: Repository data from GitHub API
            
        Returns:
            Dictionary with cleaned repository data
        """
        return {
            "id": repo.get("id"),
            "name": repo.get("name"),
            "full_name": repo.get("full_name"),
            "html_url": repo.get("html_url"),
            "description": repo.get("description"),
            "language": repo.get("language"),
            "created_at": repo.get("created_at"),
            "updated_at": repo.get("updated_at"),
            "pushed_at": repo.get("pushed_at"),
            "stargazers_count": repo.get("stargazers_count"),
            "forks_count": repo.get("forks_count"),
            "open_issues_count": repo.get("open_issues_count"),
            "license": repo.get("license", {}).get("name") if repo.get("license") else None,
            "topics": repo.get("topics", [])
        }
    
    def save_to_csv(self, repositories: List[Dict[str, Any]], filename: str) -> None:
        """
        Save repository data to a CSV file.
        
        Args:
            repositories: List of repository data
            filename: Output CSV filename
        """
        if not repositories:
            logger.warning("No repositories to save")
            return
        
        cleaned_repos = [self.extract_repository_data(repo) for repo in repositories]
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            if not cleaned_repos:
                logger.warning("No cleaned repositories to save")
                return
                
            fieldnames = cleaned_repos[0].keys()
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            
            writer.writeheader()
            writer.writerows(cleaned_repos)
            
        logger.info(f"Saved {len(cleaned_repos)} repositories to {filename}")

def main():
    # Define time ranges
    created_start = datetime.datetime(2022, 1, 1)
    created_end = datetime.datetime(2022, 1, 31)
    pushed_after = datetime.datetime(2025, 2, 1)
    
    # Initialize scraper
    scraper = GitHubScraper()
    
    try:
        # Get repositories with protection against GitHub's 1000 result limit
        repos = scraper.get_repositories_by_page_range(
            language="javascript",
            created_start=created_start,
            created_end=created_end,
            pushed_after=pushed_after,
            start_page=1,
            end_page=3,  # This will stop automatically if the 1000 result limit is reached
            per_page=100
        )
        
        # Save whatever data was collected
        scraper.save_to_csv(repos, "spider_output/javascript_projects_jan2022_active2025.csv")
    except Exception as e:
        logger.error(f"Error in main execution: {str(e)}")
        # If we have any repos collected before the error, save them
        if 'repos' in locals() and repos:
            logger.info("Saving data collected before error occurred")
            scraper.save_to_csv(repos, "spider_output/javascript_projects_jan2022_active2025_partial.csv")

if __name__ == "__main__":
    main()