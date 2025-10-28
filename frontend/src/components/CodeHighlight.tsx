import { useEffect, useRef } from 'react';
import Prism from 'prismjs';

// Import core Prism CSS
import 'prismjs/themes/prism-tomorrow.css';

// Import common languages
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-javascript';
import 'prismjs/components/prism-jsx';
import 'prismjs/components/prism-tsx';
import 'prismjs/components/prism-python';
import 'prismjs/components/prism-json';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-scss';
import 'prismjs/components/prism-markdown';
import 'prismjs/components/prism-yaml';
import 'prismjs/components/prism-sql';
import 'prismjs/components/prism-bash';

interface Props {
  code: string;
  language: string;
  showLineNumbers?: boolean;
  className?: string;
}

/**
 * Syntax highlighting component using Prism.js
 * Vite-compatible and lightweight
 */
export const CodeHighlight = ({ code, language, showLineNumbers = false, className = '' }: Props) => {
  const codeRef = useRef<HTMLElement>(null);

  useEffect(() => {
    if (codeRef.current) {
      Prism.highlightElement(codeRef.current);
    }
  }, [code, language]);

  const languageClass = `language-${language}`;

  return (
    <pre className={`${showLineNumbers ? 'line-numbers' : ''} ${className}`}>
      <code ref={codeRef} className={languageClass}>
        {code}
      </code>
    </pre>
  );
};
