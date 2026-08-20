import pytest
import sys

class OutputCatcher:
    def __init__(self):
        self.output = []
    
    def write(self, text):
        self.output.append(text)
    
    def flush(self):
        pass

if __name__ == "__main__":
    catcher = OutputCatcher()
    original_stdout = sys.stdout
    original_stderr = sys.stderr
    sys.stdout = catcher
    sys.stderr = catcher
    
    pytest.main(["tests/", "-v", "--tb=short", "--disable-warnings"])
    
    sys.stdout = original_stdout
    sys.stderr = original_stderr
    
    with open("test_results.txt", "w", encoding="utf-8") as f:
        f.write("".join(catcher.output))
