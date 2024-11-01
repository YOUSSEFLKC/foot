import os
import re
import requests
from bs4 import BeautifulSoup
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from datetime import datetime, timedelta
import unidecode  # Make sure to install this package
from dateutil import parser
from datetime import timezone
from googleapiclient.errors import HttpError
import time

# Blogger API Scope
SCOPES = ['https://www.googleapis.com/auth/blogger']
creds = None

# Authenticate Blogger API with token.json or OAuth flow
if os.path.exists('token.json'):
    creds = Credentials.from_authorized_user_file('token.json', SCOPES)

if not creds or not creds.valid:
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=8080)
    # Save credentials for the next runs
    with open('token.json', 'w') as token:
        token.write(creds.to_json())

# Initialize the Blogger API
service = build('blogger', 'v3', credentials=creds)

def delete_script_from_post(service, blog_id, post_id, script_patterns):
    """Delete specified scripts from the blog post."""
    try:
        # Retrieve the post content
        post = service.posts().get(blogId=blog_id, postId=post_id).execute()
        original_content = post['content']

        # Print original content for debugging
        print("Original Content:")
        #print(original_content)

        # Remove the specified scripts from the content
        cleaned_content = original_content
        for pattern in script_patterns:
            cleaned_content = re.sub(pattern, "", cleaned_content, flags=re.DOTALL)

        # Update the post with the cleaned content
        post['content'] = cleaned_content
        updated_post = service.posts().update(blogId=blog_id, postId=post_id, body=post).execute()

        print("Post updated successfully.")
        print("Updated Content:")
        #print(updated_post['content'])

    except Exception as e:
        print(f"An error occurred: {e}")

# Function to convert Arabic title and team names to a slug
def generate_slug(title, team1, team2):
    slug_team1 = unidecode.unidecode(team1)
    slug_team2 = unidecode.unidecode(team2)

    # Create a slug combining the team names
    slug = f"{slug_team1}-vs-{slug_team2}"
    slug = slug.lower().replace(' ', '-')
    slug = ''.join(c for c in slug if c.isalnum() or c == '-')
    print(f"Generated slug: {slug}")  # Debugging line
    return slug

# -------------------- Code 1: Scrape Syria Live TV and update a Blogger post --------------------
def run_code_1():
    def scrape_syria_live_tv():
        url = 'https://syrialive.tv/'
        response = requests.get(url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            specific_div = soup.find('div', id='tiepost-13-section-4777')
            styles = ''.join(str(style) for style in soup.find_all('style'))
            inline_styles = ''.join(
                f"<style>{element['style']}</style>" for element in specific_div.find_all(style=True)
            ) if specific_div else ""
            external_stylesheets = ''.join(
                f"<link rel='stylesheet' href='{link['href']}' />"
                for link in soup.find_all('link', rel='stylesheet')
            )
            scripts = ''.join(str(script) for script in soup.find_all('script'))

            if specific_div:
                combined_content = (
                    f"<style>{styles}</style>\n"
                    f"{external_stylesheets}\n"
                    f"{inline_styles}\n"
                    f"<script>{scripts}</script>\n"
                    f"{str(specific_div)}"
                )
                return combined_content
            else:
                print("Div not found.")
                return ""
        else:
            print(f"Failed to retrieve the page, status code: {response.status_code}")
            return ""

    def update_blogger_post(post_id, new_content):
        blog_id = '7524103465209334762'  # Your blog ID
        body = {'content': new_content}
        updated_post = service.posts().update(blogId=blog_id, postId=post_id, body=body).execute()
        print(f"Updated post: {updated_post['title']}")

    new_content = scrape_syria_live_tv()
    if new_content:
        update_blogger_post('3339729210082209615', new_content)
        

def update_urls_in_post(post_content, recent_posts):
    print("\n--- Starting to parse post content ---")
    
    # Parse the post content
    soup = BeautifulSoup(post_content, 'html.parser')

    # Log the raw post content (trimmed for readability)
    #print("\nFetched post content preview (first 1000 chars):", post_content[:1000])

    # Find all match containers in the post (each with 2 teams)
    match_divs = soup.find_all("div", class_="AF_inner asp-flex")
    print(f"\nFound {len(match_divs)} match containers in the post.")

    # If no matches are found, log this and return early
    if len(match_divs) == 0:
        print("No match containers found in the post content. Exiting.")
        return post_content

    # Loop through each match container
    for i, match_div in enumerate(match_divs, 1):
        print(f"\n--- Processing match {i} ---")
        
        # Find the team names in the match
        team_names = match_div.find_all("div", class_="AF_TeamName asp-txt-center")
        
        # Log the extracted team names
        if len(team_names) == 2:  # Ensure there are exactly 2 teams
            team_1 = team_names[0].text.strip()
            team_2 = team_names[1].text.strip()
            print(f"Team 1: {team_1}, Team 2: {team_2}")
            
            # Generate the match title in the format: "مباراة team1 vs team2"
            match_title = f"مباراة {team_1} vs {team_2}"
            print(f"Looking for recent post with title: {match_title}")

            # Find the matching recent post with the same title
            found = False
            for recent_post in recent_posts:
                print(f"Checking recent post title: {recent_post['title']}")
                
                # Ensure the team names and recent post titles match exactly
                if team_1 in recent_post['title'] and team_2 in recent_post['title']:
                    print(f"Found matching post: {recent_post['title']}, URL: {recent_post['url']}")
                    found = True

                    # Locate the relevant <a> tag using event links near match_div
                    event_link = match_div.find("a", class_="AF_EventMask")
                    
                    # If the <a> tag is not found directly, try to find it in the global event_links
                    if event_link is None:
                        print(f"Warning: <a> tag with class 'AF_EventMask' not found within match_div for {match_title}. Searching globally.")
                        
                        # Search for all event links globally to check if any need updating
                        event_links = soup.find_all("a", class_="AF_EventMask")
                        
                        # Match the event link by checking for the same href pattern (or other heuristics)
                        for link in event_links:
                            # Ensure we update only links that haven't already been updated
                            if link and not link['href'].startswith("http://55football.blogspot.com"):
                                print(f"Found global event link for {match_title} with current href: {link['href']}")
                                event_link = link
                                break

                    # Now that we have the event_link, update the URL
                    if event_link:
                        print(f"Current event link URL: {event_link['href']}")
                        print(f"Updating to new URL: {recent_post['url']}")
                        # Update the link URL to the recent post URL
                        event_link['href'] = recent_post['url']
                        print(event_link)
                    else:
                        print(f"Warning: No event link found for match {match_title}.")
                    
                    break  # Exit loop after finding the matching post and updating the URL
            if not found:
                print(f"No matching recent post found for {match_title}")
        else:
            print(f"Warning: Match {i} does not have exactly 2 teams.")
    
    # Return the updated HTML content as a string
    print("\n--- Finished processing all matches ---")
 
    return str(soup)


def get_recent_posts(blog_id, service):
    print(f"Fetching recent posts for blog ID: {blog_id}")
    
    # Make three_days_ago an offset-aware datetime object (with UTC timezone)
    three_days_ago = (datetime.now(timezone.utc) - timedelta(days=3))
    recent_posts = []
    page_token = None  # Initialize page token to handle pagination

    while True:
        # Fetch posts from the Blogger API with pagination
        posts = service.posts().list(blogId=blog_id, pageToken=page_token).execute()

        for post in posts.get('items', []):
            try:
                # Parse the published time as an offset-aware datetime
                published_time = parser.isoparse(post['published'])

                # Compare the offset-aware datetime objects
                if published_time > three_days_ago:
                    recent_posts.append({
                        'title': post['title'],
                        'url': post['url']
                    })
            except Exception as e:
                print(f"Error parsing published time for post {post['id']}: {e}")

        # Get the next page token (if available) for pagination
        page_token = posts.get('nextPageToken')

        # Break the loop if there's no more page token (i.e., we've fetched all pages)
        if not page_token:
            break

    print(f"Found {len(recent_posts)} posts published in the last 3 days.")
    return recent_posts

def initialize_service():
    creds = None

    # Load existing credentials if available
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If no valid credentials available, perform the OAuth flow
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=8080)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    # Return the Blogger API service
    return build('blogger', 'v3', credentials=creds)
# -------------------- Code 2: Scrape matches from Syria Live TV and manage Blogger posts --------------------
def run_code_2():
    def scrape_syria_live_tv():
        url = 'https://syrialive.tv/'
        print(f"Fetching data from {url}...")
        response = requests.get(url)

        if response.status_code == 200:
            print("Page fetched successfully.")
            soup = BeautifulSoup(response.text, 'html.parser')
            matches = []
            team_divs = soup.find_all('div', class_='AF_TeamName asp-txt-center')
            for i in range(0, len(team_divs), 2):
                if i + 1 < len(team_divs):
                    team1 = team_divs[i].get_text(strip=True)
                    team2 = team_divs[i + 1].get_text(strip=True)
                    title = f"مباراة {team1} vs {team2}"
                    matches.append((title, team1, team2))
            print(f"Found {len(matches)} matches.")
            return matches
        else:
            print(f"Failed to retrieve the page, status code: {response.status_code}")
            return []

    def get_all_post_titles_with_dates(blog_id):
        posts_info = {}
        page_token = None
        while True:
            posts = service.posts().list(blogId=blog_id, pageToken=page_token).execute()
            for post in posts.get('items', []):
                published_date = post['published']
                posts_info[post['title']] = published_date
            page_token = posts.get('nextPageToken')
            if not page_token:
                break
        print(f"Retrieved {len(posts_info)} existing posts with dates.")
        return posts_info

    def update_blogger_post(blog_id, post_id, title, team1, team2):
        content = f"هنا ستجد تحديث تفاصيل مباراة {team1} vs {team2}"
        body = {'title': title, 'content': content}
        print(f"Updating post with title: {title}")
        updated_post = service.posts().patch(blogId=blog_id, postId=post_id, body=body).execute()
        print(f"Updated post: {updated_post['title']}")

    def create_blogger_post(blog_id, title, slug, content):
        max_retries = 5  # Number of retries allowed
        retry_delay = 600  # 10 minutes (600 seconds) between retries

        for attempt in range(max_retries):
            try:
                print(f"Attempt {attempt + 1} to create post: {title}")
                body = {
                    'title': title,
                    'content': content,
                    'labels': ['football', 'matches'],  # Add relevant labels
                    'customMetaData': slug
                }
                new_post = service.posts().insert(blogId=blog_id, body=body).execute()
                print(f"Created new post: {new_post['title']}")
                return new_post
            except HttpError as error:
                if error.resp.status == 403:
                    print(f"Rate limit exceeded: {error}. Waiting {retry_delay // 60} minutes before retrying...")

                    # Wait before retrying (retry_delay is in seconds)
                    time.sleep(retry_delay)
                else:
                    # Log and raise any other errors that are not rate limit related
                    print(f"An error occurred: {error}")
                    raise

        print("Max retries reached. Failed to create the post after multiple attempts.")
        return None


    blog_id = '7524103465209334762'  # Your blog ID
    existing_posts = get_all_post_titles_with_dates(blog_id)
    matches = scrape_syria_live_tv()
 

    for title, team1, team2 in matches:
        if title in existing_posts:
            published_date = existing_posts[title]
            published_date = datetime.strptime(published_date, '%Y-%m-%dT%H:%M:%S%z')
            current_date = datetime.now(published_date.tzinfo)
           
        else:
            create_blogger_post(blog_id, title, team1, team2)

# -------------------- Code 3: Update URLs in existing posts --------------------

def run_code_3():
    service = initialize_service()
    
    blog_id = '7524103465209334762'  # Your blog ID
    recent_posts = get_recent_posts(blog_id, service)

    # Fetching the existing post content (for example purposes, you may want to adjust this to your needs)
    post_id = '3339729210082209615'  # Replace with your actual post ID
    post_content = service.posts().get(blogId=blog_id, postId=post_id).execute().get('content', '')

    updated_content = update_urls_in_post(post_content, recent_posts)

    # If you want to update the post with the new content, uncomment the following:
    body = {'content': updated_content}
    service.posts().update(blogId=blog_id, postId=post_id, body=body).execute()
    print(f"Updated post with new URLs.")

# -------------------- Main Process --------------------
if __name__ == "__main__":
    # Run code 1 first
    run_code_1()
    script_patterns = [
    r"<script>WebFontConfig.*?</script>",
    r"<script type=\"text/javascript\">atOptions.*?</script>",
    r"<script async=\"\" id=\"google_gtagjs-js\" src=\"https://www.googletagmanager.com/gtag/js\?id=GT-M63J9L2\" type=\"text/javascript\"></script>",
    r"<script src=\"//www.topcreativeformat.com/9456868eb208e438df9bd6b4d5b260fd/invoke.js\" type=\"text/javascript\"></script>"
]
    blog_id = '7524103465209334762' 
    post_id = '3339729210082209615' # Your blog ID
    # Call the function to delete the script from the specified post
    delete_script_from_post(service, blog_id, post_id, script_patterns)
    # Once code 1 is finished, run code 2
    run_code_2()

    # Finally, run code 3
    run_code_3()
