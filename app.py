from flask import Flask, request, render_template, jsonify
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from PIL import Image
import os
import torch
import logging
from werkzeug.utils import secure_filename
from datetime import datetime
import traceback

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = './uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Global variables
tokenizer = None
chat_model = None
conversation_history = None  # Changed to None instead of []

def load_dialogpt_model():
    """Load DialoGPT model with proper configuration"""
    global tokenizer, chat_model
    
    try:
        model_name = "microsoft/DialoGPT-medium"
        logger.info(f"Loading {model_name}...")
        
        # Load tokenizer
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        # Fix the padding token issue
        tokenizer.pad_token = tokenizer.eos_token
        
        # Load model
        chat_model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float32,
            low_cpu_mem_usage=True
        )
        
        logger.info(f"✅ Successfully loaded {model_name}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to load model: {str(e)}")
        logger.error(traceback.format_exc())
        return False

def generate_response(user_input):
    """Generate response using DialoGPT"""
    global conversation_history
    
    if not tokenizer or not chat_model:
        return "I apologize, but the AI model is not loaded properly."
    
    try:
        # Encode the new user input, add the eos_token and return a tensor in Pytorch
        new_user_input_ids = tokenizer.encode(user_input + tokenizer.eos_token, return_tensors='pt')
        
        # Append the new user input tokens to the chat history
        if conversation_history is not None:
            bot_input_ids = torch.cat([conversation_history, new_user_input_ids], dim=-1)
        else:
            bot_input_ids = new_user_input_ids
        
        # Keep conversation history manageable (limit to 1000 tokens)
        if bot_input_ids.shape[-1] > 1000:
            bot_input_ids = bot_input_ids[:, -500:]  # Keep last 500 tokens
        
        # Generate a response with attention mask
        attention_mask = torch.ones(bot_input_ids.shape, dtype=torch.long)
        
        with torch.no_grad():
            chat_history_ids = chat_model.generate(
                bot_input_ids,
                attention_mask=attention_mask,
                max_length=bot_input_ids.shape[-1] + 100,
                max_new_tokens=100,
                pad_token_id=tokenizer.eos_token_id,
                do_sample=True,
                top_p=0.92,
                top_k=50,
                temperature=0.9,
                repetition_penalty=1.3,
                no_repeat_ngram_size=3
            )
        
        # Get only the new generated tokens
        response_ids = chat_history_ids[:, bot_input_ids.shape[-1]:]
        response = tokenizer.decode(response_ids[0], skip_special_tokens=True)
        
        # Update conversation history (keep as 2D tensor)
        conversation_history = chat_history_ids
        
        # Clean up response
        response = response.strip()
        
        # If response is empty, provide a fallback
        if not response:
            fallback_responses = [
                "I see what you mean.",
                "That's interesting!",
                "Tell me more about that.",
                "I understand.",
                "Go on...",
                "Hmm, let me think about that."
            ]
            import random
            response = random.choice(fallback_responses)
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating response: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Reset conversation history on error
        conversation_history = None
        
        return "I apologize, but I encountered an error. Let's start fresh. What would you like to talk about?"

def extract_text_from_pdf(file_path):
    """Extract text from PDF file"""
    try:
        from pdfminer.high_level import extract_text
        text = extract_text(file_path)
        return text.strip()[:2000]  # Limit text length
    except ImportError:
        try:
            import PyPDF2
            with open(file_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                text = ""
                for i, page in enumerate(pdf_reader.pages[:5]):  # First 5 pages
                    text += page.extract_text() + "\n"
                return text.strip()[:2000]
        except:
            return None
    except Exception as e:
        logger.error(f"Error extracting PDF: {str(e)}")
        return None

# Initialize model
logger.info("Initializing DialoGPT model...")
model_loaded = load_dialogpt_model()

# Initialize other models (optional)
image_model = None
text_model = None

try:
    logger.info("Loading image classification model...")
    image_model = pipeline("image-classification", model="google/vit-base-patch16-224")
    logger.info("✅ Image model loaded")
except Exception as e:
    logger.warning(f"Could not load image model: {str(e)}")

try:
    logger.info("Loading text summarization model...")
    text_model = pipeline("summarization", model="sshleifer/distilbart-cnn-12-6")
    logger.info("✅ Text model loaded")
except Exception as e:
    logger.warning(f"Could not load text model: {str(e)}")

def get_greeting():
    current_hour = datetime.now().hour
    if 5 <= current_hour < 12:
        return "Good morning!"
    elif 12 <= current_hour < 18:
        return "Good afternoon!"
    elif 18 <= current_hour < 22:
        return "Good evening!"
    else:
        return "Hello!"

def get_current_time():
    return datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    try:
        # Handle file uploads
        if 'file' in request.files:
            file = request.files['file']
            if file and file.filename:
                filename = secure_filename(file.filename)
                file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(file_path)
                
                # Process images
                if filename.lower().endswith(('.png', '.jpg', '.jpeg', '.webp', '.gif')):
                    if image_model:
                        try:
                            img = Image.open(file_path).convert('RGB')
                            results = image_model(img)
                            top_predictions = results[:3]  # Get top 3
                            
                            response = "I analyzed your image. Here's what I found:\n"
                            for i, pred in enumerate(top_predictions, 1):
                                response += f"{i}. {pred['label']} (confidence: {pred['score']:.1%})\n"
                            
                            # Add conversational element
                            if results[0]['score'] > 0.8:
                                response += f"\nI'm pretty confident this is a {results[0]['label']}!"
                            else:
                                response += "\nThe image is a bit unclear, but those are my best guesses."
                            
                            os.remove(file_path)
                            return jsonify({'response': response})
                        except Exception as e:
                            logger.error(f"Image processing error: {str(e)}")
                            os.remove(file_path)
                            return jsonify({'response': "I had trouble analyzing that image. Can you try another one?"})
                    else:
                        os.remove(file_path)
                        return jsonify({'response': "Sorry, image analysis isn't available right now."})
                
                # Process PDFs
                elif filename.lower().endswith('.pdf'):
                    text = extract_text_from_pdf(file_path)
                    if text and text_model:
                        try:
                            # Summarize the PDF
                            summary = text_model(text, max_length=150, min_length=30, do_sample=False)
                            response = f"I've read your PDF document. Here's a summary:\n\n{summary[0]['summary_text']}\n\nWould you like to know anything specific about it?"
                            os.remove(file_path)
                            return jsonify({'response': response})
                        except Exception as e:
                            logger.error(f"PDF processing error: {str(e)}")
                            os.remove(file_path)
                            return jsonify({'response': f"I extracted {len(text)} characters from your PDF, but couldn't summarize it. The document seems to be about: {text[:200]}..."})
                    else:
                        os.remove(file_path)
                        return jsonify({'response': "I couldn't read that PDF file. Is it text-based or scanned images?"})
                
                # Process text files
                elif filename.lower().endswith(('.txt', '.md')):
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            text = f.read()[:2000]  # Limit to 2000 chars
                        
                        # Create a summary or response
                        word_count = len(text.split())
                        char_count = len(text)
                        
                        response = f"I've read your text file ({word_count} words, {char_count} characters).\n\n"
                        
                        if text_model and len(text) > 200:
                            try:
                                summary = text_model(text, max_length=100, min_length=20, do_sample=False)
                                response += f"Summary: {summary[0]['summary_text']}"
                            except:
                                response += f"Beginning of the file: {text[:200]}..."
                        else:
                            response += f"Content: {text[:500]}..." if len(text) > 500 else f"Content: {text}"
                        
                        os.remove(file_path)
                        return jsonify({'response': response})
                    except Exception as e:
                        logger.error(f"Text file error: {str(e)}")
                        os.remove(file_path)
                        return jsonify({'response': "I couldn't read that text file. Is it in a standard format?"})
                
                else:
                    os.remove(file_path)
                    return jsonify({'response': "I can work with images (.jpg, .png, .gif), PDFs, and text files (.txt, .md). What type of file did you want to share?"})
        
        # Handle text messages
        message = request.form.get('message', '').strip()
        
        if not message:
            return jsonify({'response': 'Please say something! 😊'}), 400
        
        logger.info(f"Received message: {message}")
        
        # Handle special queries
        if any(time_word in message.lower() for time_word in ["time", "date", "day", "clock"]):
            current_time = get_current_time()
            response = f"It's {current_time}. {get_greeting()}"
            return jsonify({'response': response})
        
        if message.lower().strip() in ["hi", "hello", "hey", "howdy", "greetings"]:
            response = f"{get_greeting()} How are you doing today?"
            return jsonify({'response': response})
        
        if "how are you" in message.lower():
            responses = [
                "I'm doing great, thanks for asking! How about you?",
                "Pretty good! Just here chatting with nice people like you. How's your day going?",
                "I'm wonderful! Thanks for asking. What's on your mind today?",
                "Can't complain! How are things with you?"
            ]
            import random
            return jsonify({'response': random.choice(responses)})
        
        # Generate AI response
        response = generate_response(message)
        logger.info(f"Generated response: {response[:80]}...")
        
        return jsonify({'response': response})
        
    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        logger.error(traceback.format_exc())
        return jsonify({'response': 'Oops! Something went wrong. Let me reset and try again. What were you saying?'}), 500
@app.route('/status', methods=['GET'])
def status():
    """Check model status"""
    conv_length = 0
    if conversation_history is not None:
        conv_length = conversation_history.shape[-1] if conversation_history.dim() > 0 else 0
    
    return jsonify({
        'chat_model': 'DialoGPT-medium' if chat_model else 'Not loaded',
        'model_loaded': chat_model is not None,
        'image_model': 'Loaded' if image_model else 'Not loaded',
        'text_model': 'Loaded' if text_model else 'Not loaded',
        'conversation_tokens': conv_length,
        'status': 'ready' if chat_model else 'not ready'
    })

@app.route('/reset', methods=['POST'])
def reset_chat():
    """Reset conversation history"""
    global conversation_history
    conversation_history = None
    logger.info("Conversation history reset")
    return jsonify({'status': 'Conversation history cleared', 'message': 'Let\'s start fresh! What would you like to talk about?'})

@app.route('/test', methods=['GET'])
def test_endpoint():
    """Test if the bot is responding"""
    if chat_model:
        test_response = generate_response("Hello")
        return jsonify({
            'status': 'ok',
            'test_response': test_response,
            'model': 'DialoGPT-medium'
        })
    else:
        return jsonify({
            'status': 'error',
            'message': 'Model not loaded'
        }), 503

if __name__ == '__main__':
    logger.info("="*50)
    logger.info("Flask ChatAI Application")
    logger.info("="*50)
    logger.info(f"Model Status: {'✅ Loaded' if model_loaded else '❌ Failed to load'}")
    logger.info(f"Image Model: {'✅ Loaded' if image_model else '❌ Not loaded'}")
    logger.info(f"Text Model: {'✅ Loaded' if text_model else '❌ Not loaded'}")
    logger.info("Starting server on http://localhost:5000")
    logger.info("="*50)
    
    app.run(debug=True, host='0.0.0.0', port=5000)