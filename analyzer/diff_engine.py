import difflib

def generate_split_diff(text1: str, text2: str):
    """
    Compares two texts line-by-line and returns two lists of HTML-formatted strings.
    The output lists have identical lengths, ensuring line-by-line alignment in a split pane.
    """
    lines1 = [line.strip() for line in text1.splitlines()]
    lines2 = [line.strip() for line in text2.splitlines()]
    
    # Clean trailing empty lines
    while lines1 and not lines1[-1]: lines1.pop()
    while lines2 and not lines2[-1]: lines2.pop()

    matcher = difflib.SequenceMatcher(None, lines1, lines2)
    left_html = []
    right_html = []
    
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            for line in lines1[i1:i2]:
                escaped = line.replace('<', '&lt;').replace('>', '&gt;')
                left_html.append(f'<div class="font-mono text-xs py-0.5 px-2 text-gray-300 whitespace-pre-wrap">{escaped or "&nbsp;"}</div>')
                right_html.append(f'<div class="font-mono text-xs py-0.5 px-2 text-gray-300 whitespace-pre-wrap">{escaped or "&nbsp;"}</div>')
        elif tag == 'delete':
            for line in lines1[i1:i2]:
                escaped = line.replace('<', '&lt;').replace('>', '&gt;')
                left_html.append(f'<div class="font-mono text-xs py-0.5 px-2 bg-red-500/15 text-red-300 border-l-2 border-red-500 whitespace-pre-wrap">{escaped or "&nbsp;"}</div>')
                right_html.append('<div class="font-mono text-xs py-0.5 px-2 bg-gray-900/10 text-transparent select-none whitespace-pre-wrap">&nbsp;</div>')
        elif tag == 'insert':
            for line in lines2[j1:j2]:
                escaped = line.replace('<', '&lt;').replace('>', '&gt;')
                left_html.append('<div class="font-mono text-xs py-0.5 px-2 bg-gray-900/10 text-transparent select-none whitespace-pre-wrap">&nbsp;</div>')
                right_html.append(f'<div class="font-mono text-xs py-0.5 px-2 bg-emerald-500/15 text-emerald-300 border-l-2 border-emerald-500 whitespace-pre-wrap">{escaped or "&nbsp;"}</div>')
        elif tag == 'replace':
            len1 = i2 - i1
            len2 = j2 - j1
            max_len = max(len1, len2)
            for k in range(max_len):
                if k < len1:
                    line = lines1[i1 + k]
                    escaped = line.replace('<', '&lt;').replace('>', '&gt;')
                    left_html.append(f'<div class="font-mono text-xs py-0.5 px-2 bg-red-500/15 text-red-300 border-l-2 border-red-500 whitespace-pre-wrap">{escaped or "&nbsp;"}</div>')
                else:
                    left_html.append('<div class="font-mono text-xs py-0.5 px-2 bg-gray-900/10 text-transparent select-none whitespace-pre-wrap">&nbsp;</div>')
                
                if k < len2:
                    line = lines2[j1 + k]
                    escaped = line.replace('<', '&lt;').replace('>', '&gt;')
                    right_html.append(f'<div class="font-mono text-xs py-0.5 px-2 bg-emerald-500/15 text-emerald-300 border-l-2 border-emerald-500 whitespace-pre-wrap">{escaped or "&nbsp;"}</div>')
                else:
                    right_html.append('<div class="font-mono text-xs py-0.5 px-2 bg-gray-900/10 text-transparent select-none whitespace-pre-wrap">&nbsp;</div>')
                    
    return left_html, right_html
