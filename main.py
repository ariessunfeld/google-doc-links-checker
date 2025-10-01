#!/usr/bin/env python3
"""
Google Docs Link Checker
Checks all hyperlinks in a public Google Doc and reports broken links.
"""

import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Tuple
import sys

class LinkChecker:
    def __init__(self, doc_url: str):
        self.doc_url = doc_url
        self.doc_id = self.extract_doc_id(doc_url)
        self.export_url = f"https://docs.google.com/document/d/{self.doc_id}/export?format=html"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def extract_doc_id(self, url: str) -> str:
        """Extract the document ID from a Google Docs URL."""
        match = re.search(r'/d/([a-zA-Z0-9-_]+)', url)
        if not match:
            raise ValueError("Invalid Google Docs URL")
        return match.group(1)
    
    def fetch_document(self) -> str:
        """Fetch the Google Doc as HTML."""
        print(f"📄 Fetching document from: {self.export_url}")
        try:
            response = self.session.get(self.export_url, timeout=10)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"❌ Error fetching document: {e}")
            sys.exit(1)
    
    def extract_links(self, html: str) -> List[Tuple[str, str]]:
        """Extract all hyperlinks from the HTML content."""
        soup = BeautifulSoup(html, 'html.parser')
        links = []
        
        for anchor in soup.find_all('a', href=True):
            url = anchor['href']
            text = anchor.get_text(strip=True)
            
            # Skip empty links and anchor links
            if url and not url.startswith('#'):
                links.append((url, text))
        
        return links
    
    def check_link(self, url: str) -> Tuple[str, int, str]:
        """Check if a link is working."""
        try:
            # Use HEAD request first (faster)
            response = self.session.head(url, timeout=10, allow_redirects=True)
            
            # Some servers don't support HEAD, try GET
            if response.status_code == 405 or response.status_code == 404:
                response = self.session.get(url, timeout=10, allow_redirects=True)
            
            status_code = response.status_code
            
            if 200 <= status_code < 400:
                status = "✅ OK"
            elif 400 <= status_code < 500:
                status = "❌ BROKEN (Client Error)"
            elif 500 <= status_code < 600:
                status = "⚠️  SERVER ERROR"
            else:
                status = f"⚠️  UNKNOWN ({status_code})"
            
            return url, status_code, status
            
        except requests.exceptions.Timeout:
            return url, 0, "⏱️  TIMEOUT"
        except requests.exceptions.SSLError:
            return url, 0, "🔒 SSL ERROR"
        except requests.exceptions.ConnectionError:
            return url, 0, "❌ CONNECTION FAILED"
        except requests.exceptions.TooManyRedirects:
            return url, 0, "🔄 TOO MANY REDIRECTS"
        except Exception as e:
            return url, 0, f"❌ ERROR: {str(e)[:50]}"
    
    def check_all_links(self, links: List[Tuple[str, str]], max_workers: int = 10):
        """Check all links concurrently."""
        print(f"\n🔍 Checking {len(links)} links...\n")
        
        results = {
            'working': [],
            'broken': [],
            'errors': []
        }
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all link checks
            future_to_link = {
                executor.submit(self.check_link, url): (url, text) 
                for url, text in links
            }
            
            # Process results as they complete
            for future in as_completed(future_to_link):
                url, text = future_to_link[future]
                check_url, status_code, status = future.result()
                
                result = {
                    'url': url,
                    'text': text,
                    'status_code': status_code,
                    'status': status
                }
                
                # Categorize results
                if '✅' in status:
                    results['working'].append(result)
                    print(f"{status} - {url}")
                elif status_code >= 400 and status_code < 600:
                    results['broken'].append(result)
                    print(f"{status} [{status_code}] - {url}")
                else:
                    results['errors'].append(result)
                    print(f"{status} - {url}")
        
        return results
    
    def print_summary(self, results: dict):
        """Print a summary of the link check results."""
        total = len(results['working']) + len(results['broken']) + len(results['errors'])
        
        print(f"\n{'='*80}")
        print(f"📊 SUMMARY")
        print(f"{'='*80}")
        print(f"Total links checked: {total}")
        print(f"✅ Working: {len(results['working'])}")
        print(f"❌ Broken: {len(results['broken'])}")
        print(f"⚠️  Errors/Timeouts: {len(results['errors'])}")
        
        if results['broken']:
            print(f"\n{'='*80}")
            print(f"❌ BROKEN LINKS")
            print(f"{'='*80}")
            for item in results['broken']:
                print(f"\nLink Text: {item['text']}")
                print(f"URL: {item['url']}")
                print(f"Status: {item['status']} [{item['status_code']}]")
        
        if results['errors']:
            print(f"\n{'='*80}")
            print(f"⚠️  LINKS WITH ERRORS")
            print(f"{'='*80}")
            for item in results['errors']:
                print(f"\nLink Text: {item['text']}")
                print(f"URL: {item['url']}")
                print(f"Status: {item['status']}")

def main():
    # Your Google Docs URL
    doc_url = "https://docs.google.com/document/d/1hWoVry0Rl5JeTL1-OE6VyOxV3C25qkfTyEP3f6MamjU/edit?tab=t.0"
    
    print("🔗 Google Docs Link Checker")
    print("="*80)
    
    try:
        # Initialize checker
        checker = LinkChecker(doc_url)
        
        # Fetch document
        html_content = checker.fetch_document()
        
        # Extract links
        links = checker.extract_links(html_content)
        
        if not links:
            print("ℹ️  No links found in the document.")
            return
        
        print(f"✅ Found {len(links)} links in the document")
        
        # Check all links
        results = checker.check_all_links(links)
        
        # Print summary
        checker.print_summary(results)
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
