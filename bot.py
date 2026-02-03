import os
import discord
import smtplib
import asyncio
import time
import random
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.utils import formataddr  # Important pour le nom d'affichage
from dotenv import load_dotenv
from main import CoverLetterGenerator  # On importe la classe du fichier main.py

# --- CONFIGURATION ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
try:
    TARGET_CHANNEL_ID = int(os.getenv("DISCORD_CHANNEL_ID"))
except:
    print("❌ Erreur : ID du salon manquant dans le .env")
    exit()

EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))

# --- FONCTION D'ENVOI EMAIL ---
def send_email(to_email, subject, body, files):
    msg = MIMEMultipart()
    
    # Force le nom d'affichage pour éviter que Gmail ne remette juste le prénom
    msg['From'] = formataddr(("Arnaud ROMAN", EMAIL_USER))
    
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.add_header('Reply-To', 'arnaud.roman@skema.edu')
    
    msg.attach(MIMEText(body, 'plain'))

    for path in files:
        if os.path.exists(path):
            with open(path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(path))
            part['Content-Disposition'] = f'attachment; filename="{os.path.basename(path)}"'
            msg.attach(part)

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_USER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USER, to_email, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"Erreur SMTP: {e}")
        return False

# --- CONFIGURATION DISCORD ---
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Initialisation du générateur
try:
    generator = CoverLetterGenerator()
    print("✅ Moteur GPT chargé.")
except Exception as e:
    print(f"❌ Erreur chargement moteur : {e}")

@client.event
async def on_ready():
    print(f'🤖 Bot prêt. Connecté sur le salon {TARGET_CHANNEL_ID}')

@client.event
async def on_message(message):
    # Ignore ses propres messages ou les mauvais salons
    if message.author == client.user: return
    if message.channel.id != TARGET_CHANNEL_ID: return

    # Vérifie s'il y a une image
    if message.attachments:
        attachment = message.attachments[0]
        if any(attachment.filename.lower().endswith(ext) for ext in ['png', 'jpg', 'jpeg', 'webp']):
            
            await message.channel.send("Image reçue. Analyse en cours...")
            
            # Sauvegarde temporaire
            image_path = f"temp_{attachment.filename}"
            await attachment.save(image_path)
            
            try:
                # 1. ANALYSE DE L'IMAGE
                job_data = generator.extract_job_details_from_image(image_path)
                
                # Suppression immédiate de l'image
                if os.path.exists(image_path): os.remove(image_path)

                if not job_data:
                    await message.channel.send("❌ Impossible de lire l'offre.")
                    return
                
                await message.channel.send(f"Offre détectée : **{job_data['job_title']}** chez **{job_data['company_name']}**")

                # 2. GESTION DE L'EMAIL (INPUT UTILISATEUR SI MANQUANT)
                recruiter_email = job_data.get('contact_email')
                
                if not recruiter_email:
                    await message.channel.send("**Aucun email trouvé.** Merci de l'écrire ci-dessous pour continuer (ou écris 'stop' pour annuler) :")
                    
                    def check(m):
                        return m.author == message.author and m.channel == message.channel
                    
                    try:
                        user_msg = await client.wait_for('message', check=check, timeout=60.0)
                        if user_msg.content.lower() == 'stop':
                            await message.channel.send("🛑 Annulé.")
                            return
                        recruiter_email = user_msg.content.strip()
                        job_data['contact_email'] = recruiter_email # Mise à jour
                        await message.channel.send(f"Email enregistré : `{recruiter_email}`")
                    except asyncio.TimeoutError:
                        await message.channel.send("Temps écoulé. Annulation.")
                        return
                else:
                    await message.channel.send(f"Destinataire : `{recruiter_email}`")

                # 3. GÉNÉRATION DES DOCUMENTS
                await message.channel.send("Rédaction de la Cover Letter et préparation de l'envoi...")
                
                # Texte du milieu
                paragraph = generator.generate_body_paragraph(job_data)
                
                # Création du PDF (Nom fixe)
                pdf_filename = "Cover Letter.pdf"
                pdf_path = generator.create_pdf(job_data, paragraph, output_filename=pdf_filename)
                
                # Contenu du mail
                subject, body = generator.generate_email_content(job_data)
                
                # 4. ENVOI
                cv_path = "CV Arnaud Roman.pdf"
                if not os.path.exists(cv_path):
                    await message.channel.send("❌ Erreur : Le fichier 'CV.pdf' est introuvable dans le dossier.")
                    return

                files_to_send = [pdf_path, cv_path]

                time.sleep(random.uniform(2, 5))
                
                success = send_email(recruiter_email, subject, body, files_to_send)

                if success:
                    await message.channel.send("**MAIL ENVOYÉ !**")
                else:
                    await message.channel.send("❌ Erreur technique lors de l'envoi SMTP.")
                
                # 5. NETTOYAGE FINAL
                if os.path.exists(pdf_path):
                    os.remove(pdf_path)

            except Exception as e:
                import traceback
                traceback.print_exc()
                await message.channel.send(f"🔥 Erreur critique : {e}")

# Lancement
if TOKEN:
    client.run(TOKEN)