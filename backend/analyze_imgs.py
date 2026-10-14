from PIL import Image
import numpy as np

imgs = {
    '8_snu_in': 'tmp_8_snu_in.png',
    '208_snu_hash': 'tmp_208_snu_hash.png',
    '213_yonsei_stem': 'tmp_213_yonsei_stem.jpg',
    '25_jasso_pamphlet': 'tmp_25_jasso_pamphlet.jpg',
}

for name, path in imgs.items():
    img = Image.open(path)
    arr = np.array(img)
    if len(arr.shape) == 3:
        # Convert to grayscale for analysis
        gray = np.dot(arr[...,:3], [0.2989, 0.5870, 0.1140])
    else:
        gray = arr
    
    # Calculate some basic metrics
    unique_colors = len(np.unique(arr.reshape(-1, arr.shape[-1] if len(arr.shape) == 3 else 1), axis=0))
    mean_brightness = np.mean(gray)
    std_brightness = np.std(gray)
    
    print(f"{name}: {img.size} {img.mode}")
    print(f"  Unique colors: {unique_colors}")
    print(f"  Mean brightness: {mean_brightness:.1f}, Std: {std_brightness:.1f}")
    print(f"  Aspect ratio: {img.size[0]/img.size[1]:.2f}")
    print()

# For the GIST image, check just the thumbnail
gist = Image.open('tmp_216_gist.jpg')
print(f"216_gist: {gist.size} {gist.mode}")
print(f"  Aspect ratio: {gist.size[0]/gist.size[1]:.2f}")
