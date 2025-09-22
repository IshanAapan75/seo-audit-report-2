# seo_audit_polars.py - Polars version
import advertools as adv
import polars as pl
import logging
import argparse
import os
import networkx as nx
import re
from urllib.parse import urlparse
from datetime import datetime
import sys
import json

# import insights module (polars version)
from seo_insights_polars import (
    interpret_meta, interpret_headings, interpret_canonicals, interpret_status,
    interpret_sitemap_vs_crawl, interpret_url_structure, interpret_redirects,
    interpret_internal_links, interpret_ngrams, interpret_robots, interpret_rendering_mode, interpret_schema
)

# ----------------- Logger -----------------
def setup_logger(log_dir):
    os.makedirs(log_dir, exist_ok=True)
    log_filename = os.path.join(log_dir, 'seo_analysis.log')

    logger = logging.getLogger("seo_audit")
    logger.setLevel(logging.INFO)
    if logger.hasHandlers():
        logger.handlers.clear()

    fh = logging.FileHandler(log_filename, mode="w", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    sh = logging.StreamHandler()
    sh.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    logger.addHandler(fh)
    logger.addHandler(sh)
    return logger

# ----------------- Crawl -----------------
def test_website_connectivity(url, logger, timeout=10):
    """Test if website is reachable before attempting crawl"""
    try:
        import requests
        response = requests.get(url, timeout=timeout, allow_redirects=True)
        logger.info(f"Website connectivity test: {url} returned status {response.status_code}")
        return response.status_code < 400
    except Exception as e:
        logger.warning(f"Website connectivity test failed for {url}: {e}")
        return False

def crawl_site(url, output_file, logger):
    logger.info(f"Starting crawl for {url}")
    
    # Test connectivity first
    if not test_website_connectivity(url, logger):
        logger.error(f"Website {url} is not reachable. Cannot proceed with crawl.")
        return None
    
    try:
        # Add custom settings for better timeout handling
        custom_settings = {
            'DOWNLOAD_TIMEOUT': 30,
            'DOWNLOAD_DELAY': 1,
            'RANDOMIZE_DOWNLOAD_DELAY': True,
            'RETRY_TIMES': 2,
            'RETRY_HTTP_CODES': [500, 502, 503, 504, 408, 429],
            'CONCURRENT_REQUESTS': 1,
            'CONCURRENT_REQUESTS_PER_DOMAIN': 1,
        }
        
        adv.crawl([url], output_file, follow_links=True, 
                  meta={}, custom_settings=custom_settings)
        logger.info(f"Crawl finished. Data saved to {output_file}")
        
        # Check if file exists and has content
        if not os.path.exists(output_file):
            logger.error(f"Crawl output file not found: {output_file}")
            return None
            
        # Read with polars
        crawldf = read_jsonl_to_polars(output_file)
        if crawldf.is_empty():
            logger.warning(f"Crawl returned no data for {url}")
            return None
            
        logger.info(f"Crawl data loaded into DataFrame. Shape: {crawldf.shape}")
        return crawldf
    except Exception as e:
        logger.error(f"An error occurred during crawling: {e}")
        return None

def read_jsonl_to_polars(file_path):
    """Read JSONL file to polars DataFrame"""
    try:
        return pl.read_ndjson(file_path)
    except:
        # Fallback for complex JSON structures
        with open(file_path, 'r', encoding='utf-8') as f:
            data = []
            for line in f:
                try:
                    data.append(json.loads(line))
                except:
                    continue
        return pl.DataFrame(data)

# ----------------- Robots.txt -----------------
def analyze_robots_txt(url, logger):
    """
    Analyze robots.txt rules for the given site.
    Returns a DataFrame with structured rules.
    """
    try:
        # Build robots.txt URL if not given
        parsed = urlparse(url)
        robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

        logger.info(f"Fetching robots.txt from {robots_url}")
        robots_df = adv.robotstxt_to_df(robots_url)

        if robots_df is None or robots_df.empty:
            logger.warning(f"No robots.txt rules found at {robots_url}")
            return None

        # Convert pandas to polars
        robots_polars = pl.from_pandas(robots_df)
        logger.info(f"Robots.txt parsed with {robots_polars.shape[0]} rules")
        return robots_polars

    except Exception as e:
        logger.error(f"Error parsing robots.txt: {e}")
        return None

# ----------------- Sitemaps -----------------
def parse_sitemap(url, logger):
    try:
        sm_df = adv.sitemap_to_df(url, recursive=True)
        if sm_df is None or sm_df.empty:
            logger.warning(f"Sitemap empty at {url}")
            return None
        # Convert to polars
        sm_polars = pl.from_pandas(sm_df)
        logger.info(f"Sitemap parsed: {url} ({len(sm_polars)} rows)")
        return sm_polars
    except Exception as e:
        logger.warning(f"Could not parse sitemap at {url}: {e}")
        return None

def get_sitemap_df(base_url, logger):
    robots_url = base_url.rstrip("/") + "/robots.txt"
    logger.info(f"Checking robots.txt for sitemaps: {robots_url}")
    sitemap_df = parse_sitemap(robots_url, logger)
    if sitemap_df is not None:
        return sitemap_df

    common_paths = [
        "/sitemap.xml", "/sitemap_index.xml", "/sitemap-index.xml",
        "/sitemap1.xml", "/sitemap-news.xml", "/sitemap-pages.xml",
        "/sitemap-posts.xml", "/sitemap-products.xml", "/sitemap_index/sitemap.xml",
    ]

    all_sitemaps = []
    for path in common_paths:
        sm_url = base_url.rstrip("/") + path
        logger.info(f"Trying fallback sitemap: {sm_url}")
        sm_df = parse_sitemap(sm_url, logger)
        if sm_df is not None:
            all_sitemaps.append(sm_df)

    if all_sitemaps:
        # Concatenate polars DataFrames
        combined = pl.concat(all_sitemaps).unique(subset=["loc"])
        logger.info(f"Collected {len(combined)} unique URLs from fallback sitemaps")
        return combined

    logger.warning("No sitemap found in robots.txt or fallback locations.")
    return None

# ----------------- Reports (polars versions) -----------------
def normalize_url(u):
    if u is None:
        return u
    u = str(u).strip().lower()
    if u.endswith("/") and len(u) > len("http://a"):
        return u.rstrip("/")
    return u

def report_meta(crawl_df, logger):
    logger.info("Generating meta report...")
    
    # Select columns and create new ones
    df = crawl_df.select(["url", "title", "meta_desc"])
    
    df = df.with_columns([
        pl.col("title").fill_null("").str.len_chars().alias("title_length"),
        pl.col("meta_desc").fill_null("").str.len_chars().alias("desc_length"),
        (pl.col("title").is_null() | (pl.col("title").fill_null("") == "")).alias("title_missing"),
        (pl.col("meta_desc").is_null() | (pl.col("meta_desc").fill_null("") == "")).alias("description_missing")
    ])
    
    logger.info(f"Meta report generated with {len(df)} rows")
    return df

def report_headings(crawl_df, logger):
    logger.info("Generating headings report...")
    
    df = crawl_df.select(["url", "h1"])
    
    # Handle h1 count logic
    df = df.with_columns([
        pl.when(pl.col("h1").dtype == pl.List(pl.Utf8))
        .then(pl.col("h1").list.len())
        .when((pl.col("h1").dtype == pl.Utf8) & (pl.col("h1").str.strip_chars() != ""))
        .then(1)
        .otherwise(0)
        .alias("h1_count")
    ])
    
    df = df.with_columns([
        (pl.col("h1_count") == 0).alias("missing_h1"),
        (pl.col("h1_count") > 1).alias("multiple_h1")
    ])
    
    logger.info(f"Headings report generated with {len(df)} rows")
    return df

def report_canonicals(crawl_df, logger):
    logger.info("Generating canonicals report...")
    
    df = crawl_df.select(["url", "canonical"])
    
    df = df.with_columns([
        pl.col("canonical").is_null().alias("canonical_missing"),
        (pl.col("canonical") == pl.col("url")).fill_null(False).alias("self_referencing")
    ])
    
    logger.info(f"Canonicals report generated with {len(df)} rows")
    return df

def report_status_codes(crawl_df, logger):
    logger.info("Generating status codes report...")
    
    cols = ["url"]
    available_cols = crawl_df.columns
    for col in ["status", "redirect_urls", "redirect_times", "redirect_reasons"]:
        if col in available_cols:
            cols.append(col)
    
    df = crawl_df.select(cols)
    logger.info(f"Status codes report generated with {len(df)} rows")
    return df

def report_sitemap_vs_crawl(sitemap_df, crawl_df, logger):
    logger.info("Generating sitemap vs crawl comparison...")
    
    # Normalize URLs in crawl data
    crawl_df_norm = crawl_df.with_columns(
        pl.col("url").map_elements(normalize_url, return_dtype=pl.Utf8).alias("url_norm")
    )
    crawl_urls = set(crawl_df_norm.select("url_norm").to_series().to_list())

    if sitemap_df is None or sitemap_df.is_empty():
        logger.warning("No sitemap data; creating empty comparison.")
        return pl.DataFrame(schema={
            "url": pl.Utf8, "in_crawl": pl.Boolean, "in_sitemap": pl.Boolean,
            "orphaned": pl.Boolean, "uncatalogued": pl.Boolean, 
            "lastmod": pl.Utf8, "sitemap": pl.Utf8
        })

    # Keep relevant columns
    keep_cols = [c for c in ["loc", "lastmod", "sitemap", "changefreq", "priority"] if c in sitemap_df.columns]
    sm_df = sitemap_df.select(keep_cols)
    
    sm_df = sm_df.with_columns(
        pl.col("loc").map_elements(normalize_url, return_dtype=pl.Utf8).alias("loc_norm")
    )
    site_urls = set(sm_df.select("loc_norm").to_series().to_list())

    all_urls = crawl_urls.union(site_urls)
    rows = []
    
    for u in all_urls:
        in_crawl = u in crawl_urls
        in_sitemap = u in site_urls
        
        if in_sitemap:
            row_data = sm_df.filter(pl.col("loc_norm") == u).row(0, named=True)
            lastmod = row_data.get("lastmod", None)
            sitemap_source = row_data.get("sitemap", None)
        else:
            lastmod = None
            sitemap_source = None
            
        rows.append({
            "url": u,
            "in_crawl": in_crawl,
            "in_sitemap": in_sitemap,
            "orphaned": in_sitemap and not in_crawl,
            "uncatalogued": in_crawl and not in_sitemap,
            "lastmod": lastmod,
            "sitemap": sitemap_source,
        })
    
    df = pl.DataFrame(rows)
    logger.info(f"Sitemap vs Crawl comparison generated with {len(df)} rows")
    return df

def build_overview(crawl_df, meta_df, headings_df, canon_df, sitemap_df, comp_df, logger):
    logger.info("Building overview report...")
    
    overview_data = {
        "total_crawled": [len(crawl_df)],
        "sitemap_urls": [len(sitemap_df) if sitemap_df is not None else 0],
        "missing_titles": [meta_df.select(pl.col("title_missing").sum()).item() if "title_missing" in meta_df.columns else 0],
        "missing_descriptions": [meta_df.select(pl.col("description_missing").sum()).item() if "description_missing" in meta_df.columns else 0],
        "multiple_h1s": [headings_df.select(pl.col("multiple_h1").sum()).item() if "multiple_h1" in headings_df.columns else 0],
        "missing_canonicals": [canon_df.select(pl.col("canonical_missing").sum()).item() if "canonical_missing" in canon_df.columns else 0],
        "orphaned_pages": [comp_df.select(pl.col("orphaned").sum()).item() if comp_df is not None and "orphaned" in comp_df.columns else 0],
        "uncatalogued_pages": [comp_df.select(pl.col("uncatalogued").sum()).item() if comp_df is not None and "uncatalogued" in comp_df.columns else 0],
    }
    
    df = pl.DataFrame(overview_data)
    logger.info(f"Overview report: {df.to_dicts()[0]}")
    return df

# ----------------- New Reports (polars versions) -----------------
def report_url_structure(crawl_df, logger):
    logger.info("Generating URL structure report...")
    try:
        # Convert to pandas for advertools, then back to polars
        urls_pandas = crawl_df.select("url").to_pandas()
        df_pandas = adv.url_to_df(urls_pandas["url"].dropna())
        df = pl.from_pandas(df_pandas)
        logger.info(f"URL structure report generated with {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Error in URL structure analysis: {e}")
        return pl.DataFrame()

def report_redirects(crawl_df, logger):
    logger.info("Generating redirect report...")
    try:
        # Convert to pandas for advertools, then back to polars
        crawl_pandas = crawl_df.to_pandas()
        df_pandas = adv.crawlytics.redirects(crawl_pandas)
        df = pl.from_pandas(df_pandas)
        logger.info(f"Redirect report generated with {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Error in redirect analysis: {e}")
        return pl.DataFrame()

def report_internal_links(crawl_df, domain_regex, logger, resolve_redirects=True):
    logger.info("Generating internal link analysis...")
    try:
        # Convert to pandas for advertools processing
        crawl_pandas = crawl_df.to_pandas()
        link_df_pandas = adv.crawlytics.links(crawl_pandas, internal_url_regex=domain_regex)
        
        if link_df_pandas is None or link_df_pandas.empty:
            logger.warning("adv.crawlytics.links returned no data.")
            return pl.DataFrame(), pl.DataFrame()

        link_df = pl.from_pandas(link_df_pandas)
        internal_links = link_df.filter(pl.col("internal").fill_null(False))
        
        if internal_links.is_empty():
            logger.warning("No internal links found after filtering.")
            return pl.DataFrame(), pl.DataFrame()

        redirect_map = {}
        if resolve_redirects:
            try:
                redirects_df_pandas = adv.crawlytics.redirects(crawl_pandas)
                if redirects_df_pandas is not None and not redirects_df_pandas.empty:
                    redirects_df = pl.from_pandas(redirects_df_pandas)
                    redirect_map = dict(zip(
                        redirects_df.select("url").to_series().to_list(),
                        redirects_df.select("redirect_url").to_series().to_list()
                    ))
            except Exception as e:
                logger.warning(f"Could not compute redirects for resolution: {e}")

        def resolve_url(u):
            if u is None:
                return u
            seen = set()
            cur = u
            while cur in redirect_map and cur not in seen:
                seen.add(cur)
                cur = redirect_map[cur]
            return cur

        if resolve_redirects and redirect_map:
            internal_links = internal_links.with_columns([
                pl.col("url").map_elements(resolve_url, return_dtype=pl.Utf8).alias("source_resolved"),
                pl.col("link").map_elements(resolve_url, return_dtype=pl.Utf8).alias("target_resolved")
            ])
        else:
            internal_links = internal_links.with_columns([
                pl.col("url").alias("source_resolved"),
                pl.col("link").alias("target_resolved")
            ])

        if domain_regex:
            internal_links = internal_links.filter(
                pl.col("target_resolved").str.contains(domain_regex).fill_null(False)
            )

        edges = internal_links.select([
            pl.col("source_resolved").alias("source"),
            pl.col("target_resolved").alias("target"),
            "text", "nofollow"
        ])

        if edges.is_empty():
            logger.warning("No internal edges remain after optional resolution/filtering.")
            return pl.DataFrame(), pl.DataFrame()

        # Convert to pandas for NetworkX
        edges_pandas = edges.to_pandas()
        G = nx.from_pandas_edgelist(edges_pandas, source="source", target="target", create_using=nx.DiGraph())

        indeg = dict(G.in_degree())
        outdeg = dict(G.out_degree())
        try:
            pr = nx.pagerank(G)
        except Exception:
            pr = {n: 0.0 for n in G.nodes()}

        nodes_data = {
            "url": list(G.nodes()),
            "in_degree": [indeg.get(n, 0) for n in G.nodes()],
            "out_degree": [outdeg.get(n, 0) for n in G.nodes()],
            "pagerank": [pr.get(n, 0) for n in G.nodes()],
        }
        
        nodes = pl.DataFrame(nodes_data).sort("pagerank", descending=True)

        logger.info(f"Internal link analysis produced {len(nodes)} nodes and {len(edges)} edges")
        return nodes, edges
    except Exception as e:
        logger.error(f"Error in internal link analysis: {e}")
        return pl.DataFrame(), pl.DataFrame()

def report_ngrams(crawl_df, logger, n=2):
    logger.info(f"Generating {n}-gram analysis (phrase_len={n})...")
    try:
        # Combine text fields
        text_data = []
        for row in crawl_df.select(["title", "meta_desc", "h1"]).to_dicts():
            text = ""
            text += str(row.get("title", "")) + " "
            text += str(row.get("meta_desc", "")) + " "
            text += str(row.get("h1", ""))
            text_data.append(text)
        
        # Use advertools for n-gram analysis
        ngram_df_pandas = adv.word_frequency(text_data, phrase_len=n)
        ngram_df = pl.from_pandas(ngram_df_pandas)
        
        logger.info(f"{n}-gram report generated with {len(ngram_df)} rows")
        return ngram_df
    except Exception as e:
        logger.error(f"Error in {n}-gram analysis: {e}")
        return pl.DataFrame()

def safe_run(func, log, name="", expected_cols=None, *args, **kwargs):
    """
    Run a function safely, catching errors and empty results.
    Returns an empty DataFrame with expected_cols if available.
    """
    try:
        df = func(*args, **kwargs)
        if df is None or (hasattr(df, "is_empty") and df.is_empty()):
            log.warning(f"{name} returned no data. Using empty DataFrame.")
            if expected_cols:
                return pl.DataFrame(schema={col: pl.Utf8 for col in expected_cols})
            return pl.DataFrame()
        return df
    except Exception as e:
        log.error(f"{name} encountered an issue: {e}. Using empty DataFrame.")
        if expected_cols:
            return pl.DataFrame(schema={col: pl.Utf8 for col in expected_cols})
        return pl.DataFrame()

def check_rendering_mode(url, logger):
    """
    Heuristic check whether site is client-side (CSR) or server-side (SSR) rendered.
    Returns a DataFrame with one row.
    """
    try:
        import requests
        from bs4 import BeautifulSoup

        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        scripts = soup.find_all("script")
        text_len = len(soup.get_text(strip=True))
        script_len = len(scripts)

        if text_len < 200 and script_len > 20:
            mode = "Likely Client-Side Rendered (CSR)"
        elif soup.find("noscript"):
            mode = "Possibly Client-Side Rendered (noscript fallback present)"
        else:
            mode = "Likely Server-Side Rendered (SSR)"

        return pl.DataFrame([{
            "url": url,
            "rendering_mode": mode,
            "text_length": text_len,
            "script_count": script_len
        }])
    except Exception as e:
        logger.error(f"Rendering mode check failed: {e}")
        return pl.DataFrame(schema={
            "url": pl.Utf8, "rendering_mode": pl.Utf8, 
            "text_length": pl.Int64, "script_count": pl.Int64
        })

def check_schema(url, logger):
    """
    Extract schema.org structured data from the homepage.
    Returns a DataFrame with schema presence and details.
    """
    try:
        import requests, json
        from bs4 import BeautifulSoup

        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        html = resp.text
        soup = BeautifulSoup(html, "html.parser")

        scripts = soup.find_all("script", type="application/ld+json")
        schema_data = []

        for s in scripts:
            try:
                data = json.loads(s.string)
                if isinstance(data, dict):
                    schema_data.append(data.get("@type", "Unknown"))
                elif isinstance(data, list):
                    schema_data.extend([d.get("@type", "Unknown") for d in data if isinstance(d, dict)])
            except Exception as e:
                logger.warning(f"Error parsing schema JSON: {e}")

        if schema_data:
            return pl.DataFrame([{
                "url": url,
                "schema_present": True,
                "schema_types": ", ".join(set(schema_data))
            }])
        else:
            return pl.DataFrame([{
                "url": url,
                "schema_present": False,
                "schema_types": ""
            }])
    except Exception as e:
        logger.error(f"Schema check failed: {e}")
        return pl.DataFrame(schema={
            "url": pl.Utf8, "schema_present": pl.Boolean, "schema_types": pl.Utf8
        })

# ----------------- Insight report builder -----------------
def save_insight_report(customer_name, output_dir, logger,
                        meta_df, headings_df, canon_df, status_df,
                        comp_df, url_struct_df, redirects_df,
                        nodes_df, edges_df,
                        ngram_1_df, ngram_2_df, ngram_3_df,
                        robots_df, rendering_df, schema_df,
                        preview_rows=5):   

    logger.info("Starting insight generation and report assembly...")

    sections = []

    def _add_section(name, func, df, *args):
        logger.info(f"Interpreting {name}...")
        try:
            if df is None or (hasattr(df, "is_empty") and df.is_empty()):
                # Neutral fallback message
                insight = {
                    "summary": f"No data was collected for {name}.",
                    "meaning": f"{name} insights are not available in this run.",
                    "red_flags": [],
                    "details": "Check logs for crawl or parsing details. This does not always indicate an issue."
                }
            else:
                insight = func(df, *args)
        except Exception as e:
            logger.warning(f"Interpretation issue in {name}: {e}")
            insight = {
                "summary": f"{name} insights could not be generated.",
                "meaning": f"{name} section did not produce data.",
                "red_flags": [],
                "details": "Check logs for details. This does not always indicate an issue."
            }

        # Clean missing values before rendering
        df_preview = None
        if df is not None and not (hasattr(df, "is_empty") and df.is_empty()):
            df_preview = df.head(preview_rows)
            # Convert to pandas for HTML rendering
            df_preview = df_preview.to_pandas().fillna("")

        sections.append((name, insight, df_preview))

    # Sequence of insights
    _add_section("Rendering_Mode", interpret_rendering_mode, rendering_df)
    _add_section("Robots", interpret_robots, robots_df)
    _add_section("Meta", interpret_meta, meta_df)
    _add_section("Headings", interpret_headings, headings_df)
    _add_section("Schema_Check", interpret_schema, schema_df)
    _add_section("Canonicals", interpret_canonicals, canon_df)
    _add_section("Status", interpret_status, status_df)
    _add_section("Sitemap_vs_Crawl", interpret_sitemap_vs_crawl, comp_df)
    _add_section("URL_Structure", interpret_url_structure, url_struct_df)
    _add_section("Redirects", interpret_redirects, redirects_df)
    _add_section("Internal_Links", interpret_internal_links, nodes_df, edges_df)
    _add_section("Ngrams_1", interpret_ngrams, ngram_1_df, 1)
    _add_section("Ngrams_2", interpret_ngrams, ngram_2_df, 2)
    _add_section("Ngrams_3", interpret_ngrams, ngram_3_df, 3)

    # Build HTML
    logger.info("Assembling HTML report...")
    html_parts = [
        f"<html><head><meta charset='utf-8'><title>SEO Audit Report - {customer_name}</title>",
        "<style>"
        "/* PDF-Friendly Blue Theme */"
        "body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.4; }"
        "h1 { color: #1e3a8a; font-size: 24px; text-align: center; margin-bottom: 20px; padding: 15px; border: 3px solid #1e3a8a; background-color: #dbeafe; }"
        "h2 { color: white; font-size: 18px; margin-top: 25px; margin-bottom: 10px; padding: 12px; background-color: #3b82f6; border-radius: 5px; }"
        "h3 { color: #2563eb; font-size: 16px; margin-top: 15px; margin-bottom: 8px; border-left: 4px solid #3b82f6; padding-left: 10px; }"
        "p { margin: 8px 0; padding: 10px; background-color: #f8fafc; border-left: 3px solid #e2e8f0; }"
        "p b { color: #1e40af; font-weight: bold; }"
        "table { border-collapse: collapse; margin: 15px 0; width: 100%; }"
        "th { background-color: #1e40af; color: white; padding: 12px 8px; font-size: 13px; font-weight: bold; text-align: left; border: 1px solid #1e40af; }"
        "td { border: 1px solid #d1d5db; padding: 10px 8px; font-size: 12px; }"
        "tr:nth-child(even) { background-color: #f1f5f9; }"
        ".redflag { color: #dc2626; font-weight: bold; background-color: #fef2f2; padding: 8px 10px; border: 2px solid #dc2626; border-radius: 4px; display: inline-block; margin: 2px 0; }"
        "ul { background-color: #fef2f2; padding: 15px 20px; border-left: 4px solid #dc2626; margin: 10px 0; }"
        "li.redflag { margin: 8px 0; color: #dc2626; font-weight: bold; }"
        ".timestamp { text-align: center; color: #6b7280; font-style: italic; margin: 20px 0; padding: 15px; border: 2px dashed #9ca3af; background-color: #f9fafb; }"
        "</style></head><body>"
    ]
    html_parts.append(f"<h1>SEO Audit Report - {customer_name}</h1>")
    html_parts.append(f"<div class='timestamp'>Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</div>")

    for name, insight, df_preview in sections:
        html_parts.append(f"<h2>{name.replace('_', ' ')}</h2>")
        html_parts.append(f"<p><b>Summary:</b> {insight['summary']}</p>")
        if insight.get("meaning"):
            html_parts.append(f"<p><b>Purpose:</b> {insight['meaning']}</p>")
        if insight.get("details"):
            html_parts.append(f"<p><b>Details:</b> {insight['details']}</p>")
        if insight.get("red_flags"):
            html_parts.append("<p><b>Red Flags:</b></p><ul>")
            for rf in insight["red_flags"]:
                html_parts.append(f"<li class='redflag'>{rf}</li>")
            html_parts.append("</ul>")
        if df_preview is not None:
            html_parts.append("<p><b>Data Preview:</b></p>")
            html_parts.append(df_preview.to_html(index=False, escape=False))

    html_parts.append("</body></html>")
    html_content = "\n".join(html_parts)

    html_file = os.path.join(output_dir, f"{customer_name}_report.html")
    try:
        with open(html_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        logger.info(f"HTML report saved: {html_file}")
    except Exception as e:
        logger.error(f"Failed saving HTML report: {e}")
        return

    # Try PDF (optional)
    pdf_file = os.path.join(output_dir, f"{customer_name}_report.pdf")
    try:
        import pypandoc
        logger.info("Converting HTML to PDF via pypandoc...")
        pypandoc.convert_text(html_content, "pdf", format="html",
                              outputfile=pdf_file, extra_args=['--standalone'])
        logger.info(f"PDF report saved: {pdf_file}")
    except Exception as e:
        logger.warning(f"PDF conversion failed or pypandoc not available: {e}. HTML is still available at {html_file}")

    print(html_content)
    sys.stdout.flush()

# ----------------- Main -----------------
def main(customer_name, url, domain_regex=None):
    customer_name = customer_name.capitalize()
    date_str = datetime.now().strftime("%Y-%m-%d")
    log_dir = f"./output/logs/{date_str}/{customer_name}"
    output_dir = os.path.join(log_dir, "seo")
    os.makedirs(output_dir, exist_ok=True)

    logger = setup_logger(log_dir)
    logger.info(f"=== SEO Audit started for {customer_name} - {url} ===")

    # ---------------- Crawl ----------------
    crawl_output_jsonl = os.path.join(output_dir, f"{customer_name}_crawl.jsonl")
    crawldf = safe_run(crawl_site, logger, "Crawl",
                       expected_cols=["url","title","meta_desc","h1","canonical","status"],
                       url=url, output_file=crawl_output_jsonl, logger=logger)
    
    try:
        crawldf.write_csv(os.path.join(output_dir, f"{customer_name}_seo.csv"))
    except Exception as e:
        logger.warning(f"Could not save crawl CSV: {e}")

    # ---------------- Robots.txt ----------------
    robots_df = safe_run(analyze_robots_txt, logger, "Robots.txt",
                         expected_cols=["directive","content"], url=url, logger=logger)

    # ---------------- Sitemap ----------------
    sitemap_df = safe_run(get_sitemap_df, logger, "Sitemap",
                          expected_cols=["loc","lastmod","sitemap"], base_url=url, logger=logger)

    schema_df = safe_run(check_schema, logger, "Schema Check",
                     expected_cols=["url","schema_present","schema_types"],
                     url=url, logger=logger)

    # ---------------- Reports ----------------
    meta_df     = safe_run(report_meta, logger, "Meta Report", expected_cols=["url","title","meta_desc"], crawl_df=crawldf, logger=logger)
    headings_df = safe_run(report_headings, logger, "Headings Report", expected_cols=["url","h1"], crawl_df=crawldf, logger=logger)
    canon_df    = safe_run(report_canonicals, logger, "Canonicals", expected_cols=["url","canonical"], crawl_df=crawldf, logger=logger)
    status_df   = safe_run(report_status_codes, logger, "Status Codes", expected_cols=["url","status"], crawl_df=crawldf, logger=logger)
    comp_df     = safe_run(report_sitemap_vs_crawl, logger, "Sitemap vs Crawl",
                           expected_cols=["url","in_crawl","in_sitemap"],
                           sitemap_df=sitemap_df, crawl_df=crawldf, logger=logger)
    overview_df = safe_run(build_overview, logger, "Overview", expected_cols=["total_crawled"],
                           crawl_df=crawldf, meta_df=meta_df, headings_df=headings_df,
                           canon_df=canon_df, sitemap_df=sitemap_df, comp_df=comp_df, logger=logger)

    # ---------------- New Reports ----------------
    url_struct_df = safe_run(report_url_structure, logger, "URL Structure", expected_cols=["url"], crawl_df=crawldf, logger=logger)
    redirects_df  = safe_run(report_redirects, logger, "Redirects", expected_cols=["url","redirect_url"], crawl_df=crawldf, logger=logger)
    
    rendering_df = safe_run(check_rendering_mode, logger, "Rendering Mode",
                        expected_cols=["url","rendering_mode","text_length","script_count"],
                        url=url, logger=logger)

    # ---------------- Internal Links ----------------
    if domain_regex is None:
        parsed = urlparse(url)
        host = parsed.netloc.split(":")[0]
        if host:
            domain_regex = re.escape(host)
            logger.info(f"Derived domain_regex = {domain_regex}")
        else:
            logger.warning("Could not derive domain_regex from URL; internal link analysis may be skipped.")

    nodes_df, edges_df = pl.DataFrame(), pl.DataFrame()
    if domain_regex:
        try:
            nodes_df, edges_df = report_internal_links(crawldf, domain_regex, logger, resolve_redirects=True)
        except Exception as e:
            logger.warning(f"Internal links not available: {e}")
            nodes_df, edges_df = pl.DataFrame(schema={"url": pl.Utf8}), pl.DataFrame(schema={"source": pl.Utf8, "target": pl.Utf8})

    # ---------------- N-Grams ----------------
    ngram_1_df = safe_run(report_ngrams, logger, "Ngrams-1", expected_cols=["word","abs_freq"], crawl_df=crawldf, logger=logger, n=1)
    ngram_2_df = safe_run(report_ngrams, logger, "Ngrams-2", expected_cols=["word","abs_freq"], crawl_df=crawldf, logger=logger, n=2)
    ngram_3_df = safe_run(report_ngrams, logger, "Ngrams-3", expected_cols=["word","abs_freq"], crawl_df=crawldf, logger=logger, n=3)

    # ---------------- Save Reports ----------------
    logger.info("Saving CSV reports...")
    try:
        if not overview_df.is_empty():   overview_df.write_csv(os.path.join(output_dir, f"{customer_name}_overview.csv"))
        if not meta_df.is_empty():       meta_df.write_csv(os.path.join(output_dir, f"{customer_name}_meta_report.csv"))
        if not headings_df.is_empty():   headings_df.write_csv(os.path.join(output_dir, f"{customer_name}_headings_report.csv"))
        if not canon_df.is_empty():      canon_df.write_csv(os.path.join(output_dir, f"{customer_name}_canonicals_report.csv"))
        if not status_df.is_empty():     status_df.write_csv(os.path.join(output_dir, f"{customer_name}_status_codes.csv"))
        if not sitemap_df.is_empty():    sitemap_df.write_csv(os.path.join(output_dir, f"{customer_name}_sitemap_full.csv"))
        if not comp_df.is_empty():       comp_df.write_csv(os.path.join(output_dir, f"{customer_name}_sitemap_vs_crawl.csv"))
        if not url_struct_df.is_empty(): url_struct_df.write_csv(os.path.join(output_dir, f"{customer_name}_url_structure.csv"))
        if not redirects_df.is_empty():  redirects_df.write_csv(os.path.join(output_dir, f"{customer_name}_redirects.csv"))
        if not nodes_df.is_empty():      nodes_df.write_csv(os.path.join(output_dir, f"{customer_name}_internal_links_nodes.csv"))
        if not edges_df.is_empty():      edges_df.write_csv(os.path.join(output_dir, f"{customer_name}_internal_links_edges.csv"))
        if not ngram_1_df.is_empty():    ngram_1_df.write_csv(os.path.join(output_dir, f"{customer_name}_ngrams_1.csv"))
        if not ngram_2_df.is_empty():    ngram_2_df.write_csv(os.path.join(output_dir, f"{customer_name}_ngrams_2.csv"))
        if not ngram_3_df.is_empty():    ngram_3_df.write_csv(os.path.join(output_dir, f"{customer_name}_ngrams_3.csv"))
        if not rendering_df.is_empty():  rendering_df.write_csv(os.path.join(output_dir, f"{customer_name}_rendering_mode.csv"))
        if not schema_df.is_empty():     schema_df.write_csv(os.path.join(output_dir, f"{customer_name}_schema_check.csv"))

    except Exception as e:
        logger.error(f"Error saving CSV reports: {e}")

    # ---------------- Build HTML Report ----------------
    save_insight_report(customer_name, output_dir, logger,
                    meta_df, headings_df, canon_df, status_df,
                    comp_df, url_struct_df, redirects_df,
                    nodes_df, edges_df,
                    ngram_1_df, ngram_2_df, ngram_3_df, robots_df,
                    rendering_df, schema_df,
                    preview_rows=5)

    logger.info("=== SEO Audit completed successfully ===")

if __name__ == "__main__":  
    parser = argparse.ArgumentParser(description="SEO Analysis Script - Polars Version")
    parser.add_argument("customer_name", type=str, help="Customer name")
    parser.add_argument("url", type=str, help="URL of the website to analyze")
    parser.add_argument("--domain_regex", type=str, help="Regex to identify internal links (optional)", default=None)
    args = parser.parse_args()
    main(args.customer_name, args.url, args.domain_regex)