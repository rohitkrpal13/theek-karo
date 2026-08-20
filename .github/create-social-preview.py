#!/usr/bin/env python3
"""Generate social preview image for GitHub repository."""

from PIL import Image, ImageDraw, ImageFont
import os

def create_social_preview():
    """Create a 1280x640 social preview image."""
    
    # Image dimensions
    width, height = 1280, 640
    
    # Create image with dark gradient background
    img = Image.new('RGB', (width, height), color=(26, 26, 46))
    draw = ImageDraw.Draw(img)
    
    # Create gradient effect manually
    for y in range(height):
        r = int(26 + (15 - 26) * (y / height))
        g = int(26 + (52 - 26) * (y / height))
        b = int(46 + (96 - 46) * (y / height))
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Draw accent lines (Indian tricolor)
    draw.rectangle([0, 0, width, 8], fill=(255, 153, 51))  # Saffron
    draw.rectangle([0, 8, width, 12], fill=(255, 255, 255))  # White
    draw.rectangle([0, 12, width, 20], fill=(19, 136, 8))  # Green
    
    # Bottom accent
    draw.rectangle([0, height - 20, width, height - 12], fill=(19, 136, 8))
    draw.rectangle([0, height - 12, width, height - 8], fill=(255, 255, 255))
    draw.rectangle([0, height - 8, width, height], fill=(255, 153, 51))
    
    # Try to load a font, fallback to default
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 64)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        font_tiny = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 18)
    except:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
        font_tiny = ImageFont.load_default()
    
    # Main title
    title = "Theek Karo"
    bbox = draw.textbbox((0, 0), title, font=font_large)
    text_width = bbox[2] - bbox[0]
    draw.text(((width - text_width) // 2, 80), title, fill=(255, 255, 255), font=font_large)
    
    # Hindi tagline
    tagline = "Make It Right"
    bbox = draw.textbbox((0, 0), tagline, font=font_medium)
    text_width = bbox[2] - bbox[0]
    draw.text(((width - text_width) // 2, 170), tagline, fill=(255, 153, 51), font=font_medium)
    
    # Description
    desc = "India-first, AI-native civic intelligence platform"
    bbox = draw.textbbox((0, 0), desc, font=font_small)
    text_width = bbox[2] - bbox[0]
    draw.text(((width - text_width) // 2, 230), desc, fill=(160, 160, 160), font=font_small)
    
    # Features
    features = "Report  •  Verify  •  Track  •  Resolve"
    bbox = draw.textbbox((0, 0), features, font=font_small)
    text_width = bbox[2] - bbox[0]
    draw.text(((width - text_width) // 2, 300), features, fill=(255, 255, 255), font=font_small)
    
    # Tech stack badges
    badges = ["FastAPI", "Next.js", "PostgreSQL", "AI/ML", "15 Languages"]
    badge_width = 120
    total_width = len(badges) * badge_width + (len(badges) - 1) * 20
    start_x = (width - total_width) // 2
    
    for i, badge in enumerate(badges):
        x = start_x + i * (badge_width + 20)
        y = 380
        
        # Draw badge background
        draw.rounded_rectangle(
            [x, y, x + badge_width, y + 35],
            radius=17,
            fill=(255, 255, 255, 30)
        )
        
        # Draw badge text
        bbox = draw.textbbox((0, 0), badge, font=font_tiny)
        text_width = bbox[2] - bbox[0]
        draw.text(
            (x + (badge_width - text_width) // 2, y + 8),
            badge,
            fill=(255, 255, 255),
            font=font_tiny
        )
    
    # GitHub URL
    url = "github.com/rohitkrpal13/theek-karo"
    bbox = draw.textbbox((0, 0), url, font=font_tiny)
    text_width = bbox[2] - bbox[0]
    draw.text(((width - text_width) // 2, height - 60), url, fill=(102, 102, 102), font=font_tiny)
    
    # Save the image
    output_path = os.path.join(os.path.dirname(__file__), "social-preview.png")
    img.save(output_path, "PNG", quality=95)
    print(f"Social preview image created: {output_path}")
    return output_path


if __name__ == "__main__":
    create_social_preview()
