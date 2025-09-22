"""
Lightweight SEO processor using minimal dependencies
"""
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
from datetime import datetime
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
import tempfile
import os

class LightweightSEOAuditor:
    def __init__(self, url):
        self.url = url
        self.domain = urlparse(url).netloc
        self.results = {}
        
    def audit_page(self, url):
        """Audit a single page"""
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            return {
                'url': url,
                'status_code': response.status_code,
                'title': soup.title.string if soup.title else None,
                'meta_description': self._get_meta_description(soup),
                'h1_count': len(soup.find_all('h1')),
                'h2_count': len(soup.find_all('h2')),
                'internal_links': self._count_internal_links(soup, url),
                'external_links': self._count_external_links(soup, url),
                'images_without_alt': self._count_images_without_alt(soup),
                'page_size': len(response.content),
                'load_time': response.elapsed.total_seconds()
            }
        except Exception as e:
            return {'url': url, 'error': str(e)}
    
    def _get_meta_description(self, soup):
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        return meta_desc.get('content') if meta_desc else None
    
    def _count_internal_links(self, soup, base_url):
        links = soup.find_all('a', href=True)
        internal_count = 0
        for link in links:
            href = link['href']
            full_url = urljoin(base_url, href)
            if urlparse(full_url).netloc == self.domain:
                internal_count += 1
        return internal_count
    
    def _count_external_links(self, soup, base_url):
        links = soup.find_all('a', href=True)
        external_count = 0
        for link in links:
            href = link['href']
            if href.startswith('http') and self.domain not in href:
                external_count += 1
        return external_count
    
    def _count_images_without_alt(self, soup):
        images = soup.find_all('img')
        return len([img for img in images if not img.get('alt')])
    
    def run_basic_audit(self):
        """Run basic SEO audit"""
        print(f"Starting basic SEO audit for {self.url}")
        
        # Audit homepage
        homepage_results = self.audit_page(self.url)
        
        # Try to find sitemap
        sitemap_urls = self._find_sitemap_urls()
        
        # Basic crawl of a few pages
        pages_to_audit = [self.url]
        if sitemap_urls:
            pages_to_audit.extend(sitemap_urls[:5])  # Limit to 5 additional pages
        
        audit_results = []
        for page_url in pages_to_audit:
            result = self.audit_page(page_url)
            audit_results.append(result)
        
        self.results = {
            'audit_date': datetime.now().isoformat(),
            'domain': self.domain,
            'pages_audited': len(audit_results),
            'results': audit_results,
            'summary': self._generate_summary(audit_results)
        }
        
        return self.results
    
    def _find_sitemap_urls(self):
        """Try to find sitemap URLs"""
        try:
            robots_url = f"{self.url.rstrip('/')}/robots.txt"
            response = requests.get(robots_url, timeout=5)
            if response.status_code == 200:
                # Simple sitemap extraction
                lines = response.text.split('\n')
                sitemap_urls = []
                for line in lines:
                    if line.lower().startswith('sitemap:'):
                        sitemap_url = line.split(':', 1)[1].strip()
                        sitemap_urls.append(sitemap_url)
                return sitemap_urls[:3]  # Limit to 3 sitemaps
        except:
            pass
        return []
    
    def _generate_summary(self, results):
        """Generate audit summary"""
        total_pages = len(results)
        pages_with_issues = 0
        common_issues = []
        
        for result in results:
            if 'error' in result:
                pages_with_issues += 1
                continue
                
            if not result.get('title'):
                common_issues.append(f"Missing title: {result['url']}")
            if not result.get('meta_description'):
                common_issues.append(f"Missing meta description: {result['url']}")
            if result.get('h1_count', 0) != 1:
                common_issues.append(f"H1 issues: {result['url']}")
        
        return {
            'total_pages': total_pages,
            'pages_with_issues': pages_with_issues,
            'common_issues': common_issues[:10]  # Top 10 issues
        }
    
    def generate_pdf_report(self, output_path):
        """Generate PDF report using ReportLab"""
        doc = SimpleDocTemplate(output_path, pagesize=letter)
        styles = getSampleStyleSheet()
        story = []
        
        # Title
        title = Paragraph(f"SEO Audit Report - {self.domain}", styles['Title'])
        story.append(title)
        story.append(Spacer(1, 12))
        
        # Summary
        summary = self.results.get('summary', {})
        story.append(Paragraph("Summary", styles['Heading1']))
        story.append(Paragraph(f"Pages Audited: {summary.get('total_pages', 0)}", styles['Normal']))
        story.append(Paragraph(f"Pages with Issues: {summary.get('pages_with_issues', 0)}", styles['Normal']))
        story.append(Spacer(1, 12))
        
        # Issues
        if summary.get('common_issues'):
            story.append(Paragraph("Common Issues", styles['Heading2']))
            for issue in summary['common_issues']:
                story.append(Paragraph(f"• {issue}", styles['Normal']))
        
        doc.build(story)
        return output_path

def create_lightweight_audit_api():
    """Create a lightweight Flask API"""
    from flask import Flask, request, send_file, jsonify
    
    app = Flask(__name__)
    
    @app.route('/process-seo-audit', methods=['POST'])
    def process_audit():
        try:
            data = request.get_json()
            email = data.get('email', '')
            
            if not email or '@' not in email:
                return jsonify({'error': 'Valid email required'}), 400
            
            domain = email.split('@')[1]
            url = f"https://{domain}"
            
            # Run lightweight audit
            auditor = LightweightSEOAuditor(url)
            results = auditor.run_basic_audit()
            
            # Generate PDF
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
                pdf_path = auditor.generate_pdf_report(tmp.name)
                
                return send_file(
                    pdf_path,
                    as_attachment=True,
                    download_name=f"{domain}_seo_audit.pdf",
                    mimetype="application/pdf"
                )
                
        except Exception as e:
            return jsonify({'error': str(e)}), 500
    
    return app

if __name__ == "__main__":
    # Test the auditor
    auditor = LightweightSEOAuditor("https://example.com")
    results = auditor.run_basic_audit()
    print(json.dumps(results, indent=2))