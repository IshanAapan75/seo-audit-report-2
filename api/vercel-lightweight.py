from flask import Flask, request, jsonify
import requests
import os
from datetime import datetime

app = Flask(__name__)

# Configuration
PROCESSING_SERVICE_URL = os.getenv('PROCESSING_SERVICE_URL', 'https://your-railway-app.com')

@app.route("/", methods=["GET"])
def health_check():
    """Health check endpoint"""
    return jsonify({
        "status": "healthy",
        "service": "SEO Audit API (Lightweight)",
        "version": "2.0.0",
        "environment": "vercel",
        "timestamp": datetime.now().isoformat()
    })

@app.route("/seo-audit", methods=["POST"])
def seo_audit():
    """
    Lightweight API that forwards requests to processing service
    """
    try:
        data = request.get_json(force=True)
        
        email = data.get("email", "")
        if not email or "@" not in email:
            return jsonify({"error": "Valid email is required"}), 400
        
        # Forward request to processing service
        response = requests.post(
            f"{PROCESSING_SERVICE_URL}/process-seo-audit",
            json=data,
            timeout=300  # 5 minutes timeout
        )
        
        if response.status_code == 200:
            # Return the PDF or HTML file
            return response.content, response.status_code, response.headers.items()
        else:
            return jsonify({
                "error": "Processing service error",
                "details": response.text
            }), response.status_code
            
    except requests.exceptions.Timeout:
        return jsonify({
            "error": "Processing timeout",
            "message": "SEO audit is taking longer than expected. Please try again."
        }), 504
    except Exception as e:
        return jsonify({
            "error": str(e),
            "message": "Failed to process SEO audit request"
        }), 500

if __name__ == "__main__":
    app.run(debug=True)