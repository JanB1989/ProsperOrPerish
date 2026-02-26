import os
import codecs

def convert_to_utf8_bom(directory):
    extensions = ('.txt', '.yml')
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(extensions):
                file_path = os.path.join(root, file)
                try:
                    # Read the file content
                    # We try to detect the encoding or just read it. 
                    # Paradox games often use UTF-8 or Windows-1252.
                    # Reading as 'utf-8-sig' (BOM) or 'utf-8' and then writing as 'utf-8-sig'
                    
                    with open(file_path, 'rb') as f:
                        content = f.read()
                    
                    # Check if it already has UTF-8 BOM
                    if content.startswith(codecs.BOM_UTF8):
                        print(f"Skipping (already UTF-8 BOM): {file_path}")
                        continue
                    
                    # Try to decode content. We'll try utf-8 first, then latin-1 as a fallback
                    try:
                        decoded_content = content.decode('utf-8')
                    except UnicodeDecodeError:
                        decoded_content = content.decode('latin-1')
                    
                    # Write back with UTF-8 BOM, ensuring we don't double up on newlines
                    # Normalize to \n first, then write with \r\n explicitly for Windows/Paradox
                    normalized_content = decoded_content.replace('\r\n', '\n').replace('\r', '\n')
                    with open(file_path, 'w', encoding='utf-8-sig', newline='\r\n') as f:
                        f.write(normalized_content)
                    
                    print(f"Converted: {file_path}")
                except Exception as e:
                    print(f"Failed to convert {file_path}: {e}")

if __name__ == "__main__":
    target_dir = r"C:\Users\Anwender\Documents\Paradox Interactive\Europa Universalis V\mod"
    if os.path.exists(target_dir):
        convert_to_utf8_bom(target_dir)
        print("Conversion complete.")
    else:
        print(f"Directory not found: {target_dir}")
