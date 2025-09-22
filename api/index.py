from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from urllib.parse import urljoin, urlparse
from datetime import datetime
import base64
from io import BytesIO
import traceback

app = Flask(__name__)
CORS(app)

class SimpleSeOAuditor:
    """Simple SEO auditor that works in serverless environments"""
    
    def __init__(self, url, customer_name):
        self.url = url
        self.customer_name = customer_name
        self.domain = urlparse(url).netloc
        self.issues = []
        self.results = {}
        
    def fetch_page(self):
        """Fetch the main page content"""
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(self.url, headers=headers, timeout=10)
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except Exception as e:
            self.issues.append(f"Failed to fetch page: {str(e)}")
            return None
    
    def check_title_tag(self, soup):
        """Check title tag optimization"""
        title = soup.find('title')
        if not title:
            self.issues.append("Missing title tag")
            return "Missing"
        
        title_text = title.get_text().strip()
        title_length = len(title_text)
        
        if title_length == 0:
            self.issues.append("Empty title tag")
            return "Empty"
        elif title_length < 30:
            self.issues.append(f"Title too short ({title_length} chars) - should be 30-60 chars")
        elif title_length > 60:
            self.issues.append(f"Title too long ({title_length} chars) - should be 30-60 chars")
        
        return title_text[:100] + "..." if len(title_text) > 100 else title_text
    
    def check_meta_description(self, soup):
        """Check meta description optimization"""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if not meta_desc:
            self.issues.append("Missing meta description")
            return "Missing"
        
        desc_content = meta_desc.get('content', '').strip()
        desc_length = len(desc_content)
        
        if desc_length == 0:
            self.issues.append("Empty meta description")
            return "Empty"
        elif desc_length < 120:
            self.issues.append(f"Meta description too short ({desc_length} chars) - should be 120-160 chars")
        elif desc_length > 160:
            self.issues.append(f"Meta description too long ({desc_length} chars) - should be 120-160 chars")
        
        return desc_content[:200] + "..." if len(desc_content) > 200 else desc_content
    
    def check_headings(self, soup):
        """Check heading structure"""
        headings = {}
        heading_issues = []
        
        for i in range(1, 7):
            h_tags = soup.find_all(f'h{i}')
            headings[f'H{i}'] = len(h_tags)
            
            if i == 1 and len(h_tags) == 0:
                heading_issues.append("Missing H1 tag")
            elif i == 1 and len(h_tags) > 1:
                heading_issues.append(f"Multiple H1 tags found ({len(h_tags)})")
        
        if heading_issues:
            self.issues.extend(heading_issues)
        
        return headings
    
    def check_images(self, soup):
        """Check image optimization"""
        images = soup.find_all('img')
        total_images = len(images)
        missing_alt = 0
        empty_alt = 0
        
        for img in images:
            alt = img.get('alt')
            if not alt:
                missing_alt += 1
            elif not alt.strip():
                empty_alt += 1
        
        if missing_alt > 0:
            self.issues.append(f"{missing_alt} images missing alt attributes")
        if empty_alt > 0:
            self.issues.append(f"{empty_alt} images have empty alt attributes")
        
        return {
            'total': total_images,
            'missing_alt': missing_alt,
            'empty_alt': empty_alt
        }
    
    def check_internal_links(self, soup):
        """Check internal linking"""
        links = soup.find_all('a', href=True)
        internal_links = 0
        external_links = 0
        
        for link in links:
            href = link['href']
            if href.startswith('http'):
                if self.domain in href:
                    internal_links += 1
                else:
                    external_links += 1
            elif href.startswith('/') or not href.startswith('#'):
                internal_links += 1
        
        return {
            'internal': internal_links,
            'external': external_links,
            'total': len(links)
        }
    
    def check_page_speed_factors(self, soup):
        """Check basic page speed factors"""
        factors = {
            'inline_css': len(soup.find_all('style')),
            'external_css': len(soup.find_all('link', rel='stylesheet')),
            'inline_js': len(soup.find_all('script', string=True)),
            'external_js': len(soup.find_all('script', src=True))
        }
        
        if factors['inline_css'] > 3:
            self.issues.append(f"Too much inline CSS ({factors['inline_css']} style tags)")
        if factors['external_css'] > 5:
            self.issues.append(f"Too many CSS files ({factors['external_css']} files)")
        if factors['external_js'] > 10:
            self.issues.append(f"Too many JavaScript files ({factors['external_js']} files)")
        
        return factors
    
    def generate_recommendations(self):
        """Generate SEO recommendations"""
        recommendations = []
        
        if "Missing title tag" in str(self.issues):
            recommendations.append("Add a descriptive title tag (30-60 characters)")
        if "Missing meta description" in str(self.issues):
            recommendations.append("Add a compelling meta description (120-160 characters)")
        if "Missing H1 tag" in str(self.issues):
            recommendations.append("Add an H1 tag to clearly define the page topic")
        if "images missing alt attributes" in str(self.issues):
            recommendations.append("Add descriptive alt text to all images for accessibility")
        if "Too many" in str(self.issues):
            recommendations.append("Optimize page loading by reducing the number of external resources")
        
        # General recommendations
        recommendations.extend([
            "Ensure your content is original and provides value to users",
            "Build quality backlinks from relevant websites",
            "Improve page loading speed for better user experience",
            "Make sure your site is mobile-friendly and responsive",
            "Create an XML sitemap and submit it to search engines"
        ])
        
        return recommendations
    
    def run_audit(self):
        """Run the complete SEO audit"""
        print(f"Starting audit for: {self.url}")
        
        soup = self.fetch_page()
        if not soup:
            print("Failed to fetch page")
            return None
        
        print("Page fetched successfully, analyzing...")
        
        try:
            self.results = {
                'title': self.check_title_tag(soup),
                'meta_description': self.check_meta_description(soup),
                'headings': self.check_headings(soup),
                'images': self.check_images(soup),
                'links': self.check_internal_links(soup),
                'page_speed': self.check_page_speed_factors(soup),
                'issues': self.issues,
                'recommendations': self.generate_recommendations()
            }
            
            print(f"Audit completed. Found {len(self.issues)} issues")
            return self.results
            
        except Exception as e:
            print(f"Error during audit: {str(e)}")
            return None

def generate_html_report(customer_name, url, audit_results):
    """Generate a beautiful HTML report"""
    
    if not audit_results:
        return f"""<!DOCTYPE html>
<html>
<head>
    <title>SEO Audit Report - {customer_name}</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 20px; background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); }}
        .error {{ background: #fef2f2; border: 1px solid #e74c3c; padding: 20px; border-radius: 8px; text-align: center; }}
    </style>
</head>
<body>
    <div class="error">
        <h1>❌ Audit Failed</h1>
        <p>Could not analyze the website: {url}</p>
        <p>Please check if the website is accessible and try again.</p>
    </div>
</body>
</html>"""
    
    # Safely get values with defaults
    issues = audit_results.get('issues', [])
    recommendations = audit_results.get('recommendations', [])
    headings = audit_results.get('headings', {})
    images = audit_results.get('images', {})
    links = audit_results.get('links', {})
    
    # Calculate score
    issues_count = len(issues)
    score = max(0, 100 - (issues_count * 15))
    
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>SEO Audit Report - {customer_name}</title>
        <meta charset="utf-8">
        <style>
            body {{ 
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; 
                margin: 0; 
                padding: 20px; 
                background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); 
                color: #333; 
                line-height: 1.6; 
            }}
            .container {{ max-width: 1000px; margin: 0 auto; }}
            h1 {{ 
                color: white; 
                font-size: 2.2em; 
                text-align: center; 
                margin-bottom: 20px; 
                padding: 25px 0; 
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                border-radius: 10px; 
                box-shadow: 0 4px 8px rgba(0,0,0,0.1); 
            }}
            h2 {{ 
                color: white; 
                font-size: 1.5em; 
                margin-top: 30px; 
                margin-bottom: 15px; 
                padding: 15px 20px; 
                background: linear-gradient(90deg, #3498db, #2980b9); 
                border-radius: 8px; 
                box-shadow: 0 3px 6px rgba(0,0,0,0.1); 
            }}
            .score {{ 
                text-align: center; 
                font-size: 3em; 
                font-weight: bold; 
                margin: 20px 0; 
                padding: 30px; 
                background: white; 
                border-radius: 15px; 
                box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                color: {'#27ae60' if score >= 80 else '#f39c12' if score >= 60 else '#e74c3c'};
            }}
            .section {{ 
                background: white; 
                margin: 20px 0; 
                padding: 20px; 
                border-radius: 10px; 
                box-shadow: 0 4px 8px rgba(0,0,0,0.1); 
            }}
            .issue {{ 
                background: #fdf2f2; 
                border: 1px solid #e74c3c; 
                padding: 10px 15px; 
                margin: 5px 0; 
                border-radius: 5px; 
                border-left: 4px solid #e74c3c; 
            }}
            .recommendation {{ 
                background: #f0f9ff; 
                border: 1px solid #3498db; 
                padding: 10px 15px; 
                margin: 5px 0; 
                border-radius: 5px; 
                border-left: 4px solid #3498db; 
            }}
            table {{ 
                width: 100%; 
                border-collapse: collapse; 
                margin: 15px 0; 
            }}
            th, td {{ 
                padding: 12px; 
                text-align: left; 
                border-bottom: 1px solid #ddd; 
            }}
            th {{ 
                background: #34495e; 
                color: white; 
            }}
            tr:nth-child(even) {{ background: #f8f9fa; }}
            .timestamp {{ 
                text-align: center; 
                color: #7f8c8d; 
                font-style: italic; 
                margin: 30px 0; 
                padding: 15px; 
                background: white; 
                border-radius: 8px; 
                border: 2px dashed #bdc3c7; 
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🔍 SEO Audit Report - {customer_name}</h1>
            
            <div class="score">
                SEO Score: {score}/100
            </div>
            
            <div class="section">
                <h2>📋 Website Overview</h2>
                <p><strong>Website:</strong> {url}</p>
                <p><strong>Company:</strong> {customer_name}</p>
                <p><strong>Analysis Date:</strong> {datetime.now().strftime('%B %d, %Y at %I:%M %p')}</p>
            </div>
            
            <div class="section">
                <h2>📊 Technical Analysis</h2>
                <table>
                    <tr><th>Element</th><th>Status</th><th>Details</th></tr>
                    <tr><td>Title Tag</td><td>{'✅' if 'Missing title' not in str(issues) else '❌'}</td><td>{audit_results.get('title', 'Not checked')}</td></tr>
                    <tr><td>Meta Description</td><td>{'✅' if 'Missing meta description' not in str(issues) else '❌'}</td><td>{audit_results.get('meta_description', 'Not checked')}</td></tr>
                    <tr><td>H1 Tag</td><td>{'✅' if headings.get('H1', 0) > 0 else '❌'}</td><td>{headings.get('H1', 0)} found</td></tr>
                    <tr><td>Images</td><td>{'✅' if images.get('missing_alt', 0) == 0 else '❌'}</td><td>{images.get('total', 0)} images, {images.get('missing_alt', 0)} missing alt text</td></tr>
                    <tr><td>Internal Links</td><td>✅</td><td>{links.get('internal', 0)} internal links found</td></tr>
                </table>
            </div>
            
            <div class="section">
                <h2>⚠️ Issues Found</h2>
                {(''.join([f'<div class="issue">❌ {issue}</div>' for issue in issues]) if issues else '<p>✅ No major issues found!</p>')}
            </div>
            
            <div class="section">
                <h2>💡 Recommendations</h2>
                {''.join([f'<div class="recommendation">💡 {rec}</div>' for rec in recommendations]) if recommendations else '<p>✅ Website looks good!</p>'}
            </div>
            
            <div class="timestamp">
                📅 Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}
            </div>
        </div>
    </body>
    </html>
    """

@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "SEO Audit API",
        "version": "2.0.0",
        "environment": "vercel",
        "timestamp": datetime.now().isoformat()
    })

@app.route("/seo-audit", methods=["POST"])
def seo_audit():
    """
    SEO Audit API endpoint - Returns download URL instead of file
    """
    try:
        data = request.get_json(force=True)
        email = data.get("email", "")
        
        if not email or "@" not in email:
            return jsonify({"error": "Valid email is required"}), 400
        
        # Extract customer info
        customer_name, domain = email.split("@", 1)
        url = f"https://{domain}"
        customer_name = domain.split(".")[0].capitalize()
        
        print(f"🔍 SEO audit request for: {customer_name}, URL: {url}")
        
        # Run SEO audit
        auditor = SimpleSeOAuditor(url, customer_name)
        results = auditor.run_audit()
        
        # Generate HTML report (even if results is None)
        html_report = generate_html_report(customer_name, url, results)
        
        if html_report is None:
            return jsonify({
                "error": "Failed to generate report",
                "message": "Could not create the SEO audit report"
            }), 500
        
        # Convert HTML to base64 for easy transfer
        try:
            html_base64 = base64.b64encode(html_report.encode('utf-8')).decode('utf-8')
        except Exception as encode_error:
            print(f"Encoding error: {encode_error}")
            return jsonify({
                "error": "Failed to encode report",
                "message": "Could not process the SEO audit report"
            }), 500
        
        # Calculate score safely
        if results and 'issues' in results:
            score = max(0, 100 - (len(results['issues']) * 15))
            issues_count = len(results['issues'])
        else:
            score = 0
            issues_count = 0
        
        # Return JSON response with download data
        return jsonify({
            "success": True,
            "message": "SEO audit completed successfully",
            "customer_name": customer_name,
            "url": url,
            "score": score,
            "issues_count": issues_count,
            "download_data": html_base64,
            "filename": f"{customer_name}_SEO_Audit_Report.html",
            "content_type": "text/html"
        })
        
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "error": str(e),
            "message": "SEO audit failed"
        }), 500

if __name__ == "__main__":
    app.run(debug=True)
