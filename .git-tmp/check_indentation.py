import tokenize
import io

def check_indentation(filename):
    with open(filename, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    for i, line in enumerate(lines):
        if line.strip() and line.startswith(' '):
            indent = len(line) - len(line.lstrip(' '))
            if indent % 4 != 0:  # Assuming 4-space indentation
                print(f"Line {i+1}: Indentation of {indent} spaces (not a multiple of 4)")
                print(f"  {line}")

if __name__ == "__main__":
    check_indentation("external_api.py")