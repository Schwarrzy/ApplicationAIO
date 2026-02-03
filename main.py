import os
import json
import base64
from datetime import date
from openai import OpenAI
from dotenv import load_dotenv
from xhtml2pdf import pisa

# Charge l'environnement si main.py est exécuté seul pour tester
load_dotenv()

class CoverLetterGenerator:
    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("❌ Clé API OPENAI manquante dans le .env")
        self.client = OpenAI(api_key=api_key)
        
        # Tes informations personnelles
        self.candidate_info = {
            "name": "Arnaud ROMAN",
            "address": "60 Rue Fedor Dostoïevski, 06902 Antibes Cedex, France",
            "phone": "+33 6 95 66 83 45",
            "email": "arnaud.roman@skema.edu",
            "skills": "VBA, Python, Structured Products, Pricing"
        }

    def _encode_image(self, image_path):
        """Encode l'image en Base64"""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def extract_job_details_from_image(self, image_path):
        """Extrait les infos de l'offre via GPT-4o Vision"""
        base64_image = self._encode_image(image_path)
        prompt = """
        Analyze this job offer image. Extract:
        1. Company Name.
        2. Job Title.
        3. Key Responsibilities (summary).
        4. Contact Email (Look carefully. If found, return it. If NOT found, return null).
        
        Respond ONLY in JSON format:
        { 
            "job_title": "...", 
            "company_name": "...", 
            "key_responsibilities": "...", 
            "contact_email": "..." 
        }
        """
        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "user", "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]}
            ],
            temperature=0.1, 
            max_tokens=400
        )
        
        try:
            content = response.choices[0].message.content.replace("```json", "").replace("```", "").strip()
            return json.loads(content)
        except Exception as e:
            print(f"Erreur parsing JSON : {e}")
            return None

    def generate_body_paragraph(self, job_data):
        """Génère le paragraphe central adapté"""
        prompt = f"""
        Write the middle body paragraph for a cover letter (approx 6-8 lines) in English.
        
        Context:
        - Role: {job_data['job_title']} at {job_data['company_name']}.
        - Key Tasks: {job_data['key_responsibilities']}.
        - Candidate Background: Market finance, structured products (internships at i-Kapital & EFG AM), VBA/Python coding skills.
        
        Goal: 
        Connect the candidate's specific background to the company's needs. Show enthusiasm for {job_data['company_name']}.
        Style: Formal, "Investment Banking" style (Morgan Stanley style).
        """
        response = self.client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7
        )
        return response.choices[0].message.content.strip()

    def generate_email_content(self, job_data):
        """Prépare le sujet et le corps du mail d'accompagnement"""
        email = job_data.get('contact_email')
        recruiter_name = "Hiring Team"
        
        # Tentative de deviner le nom via l'email
        if email and "@" in email:
            local_part = email.split('@')[0]
            if "." in local_part:
                possible_name = local_part.split('.')[0]
                if possible_name.lower() not in ['contact', 'info', 'rh', 'recruitment', 'careers']:
                    recruiter_name = possible_name.capitalize()

        subject = f"Application – {job_data['job_title']} - Arnaud"
        
        body = f"""Dear {recruiter_name},

I am writing to apply for the {job_data['job_title']} position.

Currently pursuing a Master’s degree in Finance, I am highly motivated to join a dynamic and entrepreneurial environment such as {job_data['company_name']}. 
This opportunity strongly aligns with my interest in financial markets, sales activities, and cross-asset solutions.

Please find attached my CV and cover letter for your consideration. I would be pleased to further discuss my application and motivation.

Kind regards,
Arnaud Roman"""

        return subject, body

    def create_pdf(self, job_data, adaptive_paragraph, output_filename="Cover Letter.pdf"):
        """Génère le PDF avec le style PRO (Texte justifié, marges, espacements)"""
        today_date = date.today().strftime("%B %d, %Y")
        
        # Gestion de la signature
        sig_path = "signature.png"
        if os.path.exists(sig_path):
            signature_html = f'<img src="{sig_path}" style="width: 150px; height: auto; margin-top: 20px;">'
        else:
            signature_html = ""

        html_content = f"""
        <html>
        <head>
            <style>
                @page {{ margin: 2.5cm 2.5cm; }}
                body {{ 
                    font-family: 'Helvetica', 'Arial', sans-serif; 
                    font-size: 11pt; 
                    line-height: 1.5; 
                    color: #000; 
                }}
                .header-contact {{ 
                    text-align: right; 
                    margin-bottom: 40px; 
                    font-size: 10pt;
                }}
                .name {{ 
                    font-weight: bold; 
                    font-size: 12pt;
                    margin-bottom: 5px;
                    text-transform: uppercase;
                }}
                .meta-table {{ 
                    width: 100%; 
                    margin-bottom: 30px; 
                    border: none; 
                }}
                .content {{ 
                    text-align: justify; 
                }}
                /* Espacement entre les paragraphes */
                .content p {{
                    margin-bottom: 15px; 
                    text-align: justify;
                }}
                .signature {{ 
                    margin-top: 50px; 
                }}
            </style>
        </head>
        <body>
            <div class="header-contact">
                <div class="name">{self.candidate_info['name']}</div>
                {self.candidate_info['email']}<br>
                {self.candidate_info['phone']}<br>
                {self.candidate_info['address']}
            </div>

            <table class="meta-table">
                <tr>
                    <td style="text-align: left; width: 50%;">Dear Hiring Manager,</td>
                    <td style="text-align: right; width: 50%;">{today_date}</td>
                </tr>
            </table>

            <div class="content">
                <p>I am writing to express my strong interest in the {job_data['job_title']} position at <strong>{job_data['company_name']}</strong>. With a solid background in structured products and market finance, developed through previous internships at i-Kapital in Paris and EFG AM in Monaco, I am eager to bring my technical skills to your team.</p>
                
                <p>{adaptive_paragraph}</p>
                
                <p>Thank you for considering my application. I look forward to the opportunity to discuss how my background aligns with {job_data['company_name']}’s goals.</p>
            </div>

            <div class="signature">
                Yours sincerely,<br>
                {self.candidate_info['name']}<br>
                {signature_html}
            </div>
        </body>
        </html>
        """
        
        with open(output_filename, "w+b") as result_file:
            pisa.CreatePDF(html_content, dest=result_file)
        return output_filename