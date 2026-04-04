import os
import logging
from PIL import Image
from flask import current_app
from werkzeug.utils import secure_filename

logger = logging.getLogger(__name__)


ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_image(file, folder='uploads', filename=None):
    if not file or not allowed_file(file.filename):
        return None
    
    try:
        if filename is None:
            from datetime import datetime
            fname = secure_filename(file.filename)
            ext = fname.rsplit('.', 1)[1].lower() if '.' in fname else 'jpg'
            filename = f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{fname[:20]}.{ext}"
        
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        
        img = Image.open(file)
        
        if img.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', img.size, (255, 255, 255))
            background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
            img = background
        elif img.mode != 'RGB':
            img = img.convert('RGB')
        
        max_size = current_app.config.get('IMAGE_SIZE', (1920, 1080))
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        quality = current_app.config.get('IMAGE_QUALITY', 85)
        img.save(filepath, 'JPEG', quality=quality, optimize=True)
        
        logger.info(f'Image saved: {filename}')
        return filename
        
    except Exception as e:
        logger.error(f'Failed to save image: {str(e)}')
        return None


def delete_image(filename):
    if not filename:
        return False
    
    try:
        filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(filepath):
            os.remove(filepath)
            logger.info(f'Image deleted: {filename}')
            return True
    except Exception as e:
        logger.error(f'Failed to delete image: {str(e)}')
    return False


def get_image_url(filename):
    if not filename:
        return None
    from flask import url_for
    return url_for('main.uploaded_file', filename=filename)
