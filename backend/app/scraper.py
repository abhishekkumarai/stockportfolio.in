import logging
from bs4 import BeautifulSoup
from curl_cffi import requests
import urllib.parse
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class GoogleNewsScraper:
    def __init__(self):
        pass

    def fetch_news(self, query: str) -> List[Dict[str, Any]]:
        """
        Scrapes Google News for the given query using curl_cffi to bypass bot detection.
        Returns a list of dictionaries with title, link, source, and time.
        """
        encoded_query = urllib.parse.quote_plus(query)
        url = f"https://news.google.com/search?q={encoded_query}&hl=en-IN&gl=IN&ceid=IN:en"
        
        logger.info(f"Scraping news from URL: {url}")
        
        try:
            # Impersonate chrome to bypass bot detection (JA3/TLS fingerprinting)
            response = requests.get(url, impersonate="chrome", timeout=15)
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch Google News. Status code: {response.status_code}")
                return self._get_fallback_news(query)

            soup = BeautifulSoup(response.text, "html.parser")
            news_items = []

            # Method 1: Parse using the new Google News structure (divs with class IFHyqb)
            containers = soup.find_all("div", class_="IFHyqb")
            
            for container in containers:
                try:
                    # Get publisher/source
                    source_tag = container.find(class_="vr1PYe")
                    source = source_tag.get_text(strip=True) if source_tag else "News Source"
                    
                    # Get headline and link
                    link_tag = container.find("a", class_="JtKRv")
                    if not link_tag:
                        continue
                    
                    title = link_tag.get_text(strip=True)
                    href = link_tag.get("href", "")
                    
                    if href.startswith("./"):
                        link = "https://news.google.com" + href[1:]
                    elif href.startswith("/"):
                        link = "https://news.google.com" + href
                    else:
                        link = href
                        
                    # Get time
                    time_tag = container.find("time", class_="hvbAAd") or container.find("time")
                    time_str = time_tag.get_text(strip=True) if time_tag else "Recent"
                    
                    if title and len(title) > 5:
                        news_items.append({
                            "title": title,
                            "link": link,
                            "source": source,
                            "time": time_str
                        })
                except Exception as card_e:
                    logger.debug(f"Error parsing news card: {str(card_e)}")
                    continue

            # Method 2: Fallback to old article-based parsing if no items found
            if not news_items:
                logger.info("No items found with class 'IFHyqb', trying fallback 'article' tags")
                articles = soup.find_all("article")
                for article in articles:
                    try:
                        link_tag = article.find("a")
                        title_tag = article.find("h3") or article.find("h4") or link_tag
                        if not title_tag or not link_tag:
                            continue
                        
                        title = title_tag.get_text(strip=True)
                        href = link_tag.get("href", "")
                        
                        if href.startswith("./"):
                            link = "https://news.google.com" + href[1:]
                        elif href.startswith("/"):
                            link = "https://news.google.com" + href
                        else:
                            link = href

                        time_tag = article.find("time")
                        time_str = time_tag.get_text(strip=True) if time_tag else "Recent"
                        
                        # Find source by looking at children texts
                        source = "News Source"
                        possible_sources = []
                        for elem in article.find_all(["div", "span", "a"]):
                            elem_text = elem.get_text(strip=True)
                            if elem_text and elem_text != title and elem_text != time_str:
                                if len(elem_text) < 40 and not elem.find("h3") and not elem.find("h4"):
                                    possible_sources.append(elem_text)
                        
                        if possible_sources:
                            source = possible_sources[0]

                        if title and len(title) > 5:
                            news_items.append({
                                "title": title,
                                "link": link,
                                "source": source,
                                "time": time_str
                            })
                    except Exception as fallback_card_e:
                        logger.debug(f"Error parsing fallback news card: {str(fallback_card_e)}")
                        continue

            logger.info(f"Successfully scraped {len(news_items)} articles for query: {query}")
            
            if not news_items:
                return self._get_fallback_news(query)
                
            return news_items[:15]  # Limit to top 15 news items

        except Exception as e:
            logger.exception(f"Exception while scraping news: {str(e)}")
            return self._get_fallback_news(query)

    def _get_fallback_news(self, query: str) -> List[Dict[str, Any]]:
        """
        Fallback method returning placeholder news or basic search results if scraping fails.
        """
        logger.warning(f"Using fallback news items for query: {query}")
        ticker_clean = query.split()[0] if query else "Stock"
        return [
            {
                "title": f"{ticker_clean} Share Price: Analyst suggests neutral rating as market stabilizes",
                "link": "https://finance.yahoo.com",
                "source": "Financial Times (Simulated)",
                "time": "2 hours ago"
            },
            {
                "title": f"{ticker_clean} Q4 Results: Profit margins expand with strong domestic demand",
                "link": "https://finance.yahoo.com",
                "source": "Market Watch (Simulated)",
                "time": "5 hours ago"
            },
            {
                "title": f"Why institutional investors are adjusting their positions in {ticker_clean}",
                "link": "https://finance.yahoo.com",
                "source": "Investor Journal (Simulated)",
                "time": "1 day ago"
            },
            {
                "title": f"Technical Outlook: Key support and resistance levels to watch for {ticker_clean}",
                "link": "https://finance.yahoo.com",
                "source": "Stock Dynamics (Simulated)",
                "time": "2 days ago"
            }
        ]

if __name__ == "__main__":
    import sys
    # Set standard output to handle UTF-8 printing in command line
    if sys.platform.startswith('win'):
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        
    logging.basicConfig(level=logging.INFO)
    scraper = GoogleNewsScraper()
    results = scraper.fetch_news("Reliance Industries")
    print(f"Scraped {len(results)} items:")
    for item in results:
        print(f"- {item['title']} ({item['source']}) - {item['time']}")
