import os
import csv
import subprocess
import sys

def clone_github_repos(csv_file):
    # Create the 'repos' directory if it doesn't exist
    if not os.path.exists('repos/post-repos'):
        os.makedirs('repos/post-repos')
    
    # Try different encodings to read the CSV file
    encodings = ['utf-8', 'latin1', 'utf-16', 'cp1252']
    
    for encoding in encodings:
        try:
            # Read the CSV file with specified encoding
            with open(csv_file, 'r', encoding=encoding) as file:
                # Try to read a small sample to confirm encoding works
                sample = file.read(4096)
                file.seek(0)
                
                csv_reader = csv.DictReader(file)
                
                # Check if the 'html_url' column exists
                if 'html_url' not in csv_reader.fieldnames:
                    print(f"Warning: 'html_url' column not found with {encoding} encoding. Trying another encoding...")
                    continue
                
                # Column found, proceed with cloning
                print(f"Successfully opened file with {encoding} encoding")
                
                # Clone each repository
                for row in csv_reader:
                    repo_url = row['html_url']
                    # Skip if URL is empty
                    if not repo_url:
                        continue
                        
                    repo_name = repo_url.split('/')[-1]
                    
                    print(f"Cloning {repo_name} from {repo_url}...")
                    
                    # Clone the repository
                    try:
                        subprocess.run(['git', 'clone', repo_url, f'repos/post-repos/{repo_name}'], 
                                      check=True, 
                                      stdout=subprocess.PIPE, 
                                      stderr=subprocess.PIPE)
                        print(f"Successfully cloned {repo_name}")
                    except subprocess.CalledProcessError as e:
                        print(f"Failed to clone {repo_name}: {e.stderr.decode()}")
                
                # We've successfully processed the file, so return
                return
                
        except UnicodeDecodeError:
            print(f"Failed to open file with {encoding} encoding. Trying another...")
        except Exception as e:
            print(f"Error with {encoding} encoding: {str(e)}")
    
    # If we get here, none of the encodings worked
    print("Error: Could not open the CSV file with any of the attempted encodings.")
    sys.exit(1)

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python clone_repos.py <csv_file>")
        sys.exit(1)
    
    csv_file = sys.argv[1]
    clone_github_repos(csv_file)
    print("All repositories have been processed.")