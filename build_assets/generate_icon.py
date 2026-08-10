import os
from PIL import Image, ImageDraw, ImageFont

def generate_app_icon():
    """Generates a professional modern app icon and saves it as .ico."""
    # Create a base image (256x256) with transparency
    size = (256, 256)
    img = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    # 1. Draw rounded rectangle background (dark green gradient look, using solid color here for simplicity)
    # Background color: Roz WhatsApp Green #128C7E
    bg_color = (18, 140, 126, 255)
    draw.rounded_rectangle(
        [(10, 10), (246, 246)], 
        radius=48, 
        fill=bg_color
    )
    
    # 2. Draw white speech bubble
    # Main oval
    draw.ellipse([(50, 50), (206, 206)], fill=(255, 255, 255, 255))
    # Speech bubble tail triangle
    draw.polygon([(70, 180), (50, 215), (105, 200)], fill=(255, 255, 255, 255))
    
    # 3. Draw a inner circular outline or letter "R"
    # To avoid font dependencies (since fonts like Arial might not load identically on every system),
    # we can draw the letter 'R' using lines/shapes or try loading a default font.
    # Drawing 'R' manually is bulletproof and doesn't rely on OS-specific fonts!
    # Let's draw 'R' manually to be extremely robust!
    
    # Drawing letter R inside the circle:
    # Circle bounds are (50,50) to (206,206), center is (128, 128)
    # We will draw a green R. Green color #075E54
    r_color = (7, 94, 84, 255)
    
    # Stem of R: vertical line from x=100, y=85 to y=170, thickness 16
    draw.line([(100, 85), (100, 170)], fill=r_color, width=16)
    
    # Top curve of R (semicircle): from y=85 to y=130, looping right to x=150
    # Semicircle outline by drawing arcs
    # Let's draw the top loop of R using rounded rect
    draw.rounded_rectangle(
        [(100, 85), (155, 130)],
        radius=15,
        outline=r_color,
        width=16
    )
    
    # Leg of R: diagonal line from x=120, y=130 to x=155, y=170, thickness 16
    draw.line([(120, 130), (155, 170)], fill=r_color, width=16)
    
    # Save the image as icon.ico (ICO format supports multiple sizes, Pillow handles it automatically)
    os.makedirs("build_assets", exist_ok=True)
    icon_path = os.path.join("build_assets", "icon.ico")
    
    # Save sizes 16x16, 32x32, 48x48, 64x64, 128x128, 256x256 in the ICO container
    img.save(
        icon_path, 
        format="ICO", 
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    )
    print(f"Icon generated successfully at: {icon_path}")

if __name__ == "__main__":
    generate_app_icon()
