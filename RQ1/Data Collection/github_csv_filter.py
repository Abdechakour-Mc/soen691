import csv
import logging
import argparse
from typing import List, Dict, Any

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("logs/github_filter.log"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

class GitHubCSVFilter:
    """
    Filter GitHub repository data from CSV files based on specific criteria.
    """
    
    def __init__(self, input_file: str):
        """
        Initialize the filter with the input CSV file path.
        
        Args:
            input_file: Path to the input CSV file
        """
        self.input_file = input_file
        self.repositories = []
    
    def load_csv(self) -> None:
        """
        Load repository data from the CSV file.
        """
        try:
            with open(self.input_file, 'r', encoding='utf-8') as csvfile:
                reader = csv.DictReader(csvfile)
                self.repositories = list(reader)
                
            logger.info(f"Loaded {len(self.repositories)} repositories from {self.input_file}")
        except Exception as e:
            logger.error(f"Error loading CSV file: {e}")
            raise
    
    def filter_repositories(self, 
                           min_stars: int = 0, 
                           min_open_issues: int = 0,
                           min_topics: int = 0) -> List[Dict[str, Any]]:
        """
        Filter repositories based on criteria.
        
        Args:
            min_stars: Minimum number of stargazers
            min_open_issues: Minimum number of open issues
            min_topics: Minimum number of topics
            
        Returns:
            List of filtered repositories
        """
        filtered_repos = []
        
        for repo in self.repositories:
            # Convert string values to appropriate types
            stars = int(repo.get('stargazers_count', 0))
            open_issues = int(repo.get('open_issues_count', 0))
            
            # Handle topics (stored as a string representation of a list)
            topics_str = repo.get('topics', '[]')
            try:
                # Clean up the string and convert to list
                topics_str = topics_str.strip('[]').replace("'", "").replace('"', '')
                topics = [t.strip() for t in topics_str.split(',') if t.strip()]
                topic_count = len(topics)
            except Exception as e:
                logger.warning(f"Error parsing topics for {repo.get('full_name')}: {e}")
                topic_count = 0
            
            # Apply filters
            if (stars >= min_stars and 
                open_issues >= min_open_issues and 
                topic_count >= min_topics):
                filtered_repos.append(repo)
        
        logger.info(f"Filtered {len(filtered_repos)} repositories out of {len(self.repositories)}")
        return filtered_repos
    
    def save_to_csv(self, repositories: List[Dict[str, Any]], output_file: str) -> None:
        """
        Save filtered repository data to a CSV file.
        
        Args:
            repositories: List of repository data
            output_file: Output CSV filename
        """
        if not repositories:
            logger.warning("No repositories to save")
            return
        
        try:
            with open(output_file, 'w', newline='', encoding='utf-8') as csvfile:
                fieldnames = repositories[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                
                writer.writeheader()
                writer.writerows(repositories)
                
            logger.info(f"Saved {len(repositories)} repositories to {output_file}")
        except Exception as e:
            logger.error(f"Error saving CSV file: {e}")
            raise

def main():
    # Set up argument parsing
    parser = argparse.ArgumentParser(description='Filter GitHub repository data from CSV files')
    parser.add_argument('input_file', help='Input CSV file path')
    parser.add_argument('output_file', help='Output CSV file path')
    parser.add_argument('--min-stars', type=int, default=0, help='Minimum number of stars (default: 10)')
    parser.add_argument('--min-issues', type=int, default=0, help='Minimum number of open issues (default: 5)')
    parser.add_argument('--min-topics', type=int, default=0, help='Minimum number of topics (default: 1)')
    
    args = parser.parse_args()
    
    # Initialize and run filter
    try:
        filter_tool = GitHubCSVFilter(args.input_file)
        filter_tool.load_csv()
        
        filtered_repos = filter_tool.filter_repositories(
            min_stars=args.min_stars,
            min_open_issues=args.min_issues,
            min_topics=args.min_topics
        )
        
        filter_tool.save_to_csv(filtered_repos, args.output_file)
        
        logger.info(f"Successfully filtered repositories: {len(filtered_repos)} met the criteria")
        
    except Exception as e:
        logger.error(f"Error during filtering process: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())