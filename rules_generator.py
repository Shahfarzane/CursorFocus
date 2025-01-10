import os
import json
from typing import Dict, Any, List
from datetime import datetime
import google.generativeai as genai
import re
from rules_analyzer import RulesAnalyzer
from dotenv import load_dotenv

class RulesGenerator:
    def __init__(self, project_path: str):
        self.project_path = project_path
        self.analyzer = RulesAnalyzer(project_path)
        
        # Load environment variables from .env
        load_dotenv()
        
        # Initialize Gemini AI
        try:
            api_key = os.environ.get("GEMINI_API_KEY")
            if not api_key:
                raise ValueError("GEMINI_API_KEY is required")

            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(
                model_name="gemini-2.0-flash-exp",
                generation_config={
                    "temperature": 0.7,
                    "top_p": 0.95,
                    "top_k": 40,
                    "max_output_tokens": 8192,
                }
            )
            self.chat_session = self.model.start_chat(history=[])
            
        except Exception as e:
            print(f"\n⚠️ Error when initializing Gemini AI: {e}")
            raise

    def _get_timestamp(self) -> str:
        """Get current timestamp in standard format."""
        return datetime.now().strftime('%B %d, %Y at %I:%M %p')

    def _analyze_project_structure(self) -> Dict[str, Any]:
        """Analyze project structure and collect detailed information."""
        structure = {
            'files': [],
            'dependencies': {},
            'frameworks': [],
            'languages': {},
            'test_files': [],
            'config_files': [],
            'doc_files': [],
            'code_contents': {},
            'patterns': {
                'classes': [],
                'functions': [],
                'imports': [],
                'error_handling': [],
                'tests': [],
                'configurations': [],
                'naming_patterns': {},  # Track naming conventions
                'code_organization': [], # Track code organization patterns
                'docstring_patterns': [], # Track documentation patterns
                'variable_patterns': [], # Track variable naming and usage
                'function_patterns': [], # Track function patterns
                'class_patterns': [],    # Track class patterns
                'test_patterns': [],     # Track testing patterns
                'error_patterns': [],    # Track error handling patterns
                'performance_patterns': [] # Track performance patterns
            }
        }

        # Analyze each file
        for root, _, files in os.walk(self.project_path):
            if any(x in root for x in ['node_modules', 'venv', '.git', '__pycache__', 'build', 'dist']):
                continue

            for file in files:
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, self.project_path)
                
                # Analyze code files
                if file.endswith(('.py', '.js', '.ts', '.java', '.cpp')):
                    structure['files'].append(rel_path)
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            structure['code_contents'][rel_path] = content
                            
                            # Analyze Python code
                            if file.endswith('.py'):
                                # Find imports and dependencies
                                imports = re.findall(r'^(?:from|import)\s+([a-zA-Z0-9_\.]+)', content, re.MULTILINE)
                                structure['dependencies'].update({imp: True for imp in imports})
                                structure['patterns']['imports'].extend(imports)
                                
                                # Find classes and their patterns
                                classes = re.findall(r'class\s+(\w+)(?:\(.*?\))?:', content)
                                structure['patterns']['classes'].extend(classes)
                                
                                # Analyze class patterns
                                class_patterns = re.finditer(r'class\s+(\w+)(?:\((.*?)\))?\s*:', content)
                                for match in class_patterns:
                                    class_name = match.group(1)
                                    inheritance = match.group(2) if match.group(2) else ''
                                    structure['patterns']['class_patterns'].append({
                                        'name': class_name,
                                        'inheritance': inheritance,
                                        'file': rel_path
                                    })
                                
                                # Find and analyze functions
                                function_patterns = re.finditer(r'def\s+(\w+)\s*\((.*?)\)(?:\s*->\s*([^:]+))?\s*:', content)
                                for match in function_patterns:
                                    func_name = match.group(1)
                                    params = match.group(2)
                                    return_type = match.group(3) if match.group(3) else None
                                    structure['patterns']['function_patterns'].append({
                                        'name': func_name,
                                        'parameters': params,
                                        'return_type': return_type,
                                        'file': rel_path
                                    })
                                
                                # Analyze docstring patterns
                                docstrings = re.finditer(r'"""(.*?)"""', content, re.DOTALL)
                                for match in docstrings:
                                    structure['patterns']['docstring_patterns'].append({
                                        'content': match.group(1).strip(),
                                        'file': rel_path
                                    })
                                
                                # Analyze variable patterns
                                variables = re.finditer(r'(\w+)\s*(?::[\s\w\[\],]*?)?\s*=\s*([^#\n]+)', content)
                                for match in variables:
                                    var_name = match.group(1)
                                    var_value = match.group(2).strip()
                                    if not var_name.isupper():  # Skip constants
                                        structure['patterns']['variable_patterns'].append({
                                            'name': var_name,
                                            'value_type': var_value,
                                            'file': rel_path
                                        })
                                
                                # Analyze error handling
                                error_blocks = re.finditer(r'try\s*:.*?except\s+(\w+)(?:\s+as\s+(\w+))?\s*:', content, re.DOTALL)
                                for match in error_blocks:
                                    exception_type = match.group(1)
                                    exception_var = match.group(2) if match.group(2) else None
                                    structure['patterns']['error_patterns'].append({
                                        'exception_type': exception_type,
                                        'exception_var': exception_var,
                                        'file': rel_path
                                    })
                                
                                # Analyze test patterns
                                if '_test' in file or 'test_' in file:
                                    test_functions = re.finditer(r'def\s+(test_\w+)\s*\((.*?)\)', content)
                                    for match in test_functions:
                                        test_name = match.group(1)
                                        test_params = match.group(2)
                                        structure['patterns']['test_patterns'].append({
                                            'name': test_name,
                                            'parameters': test_params,
                                            'file': rel_path
                                        })
                                
                                # Analyze performance patterns
                                # Look for common performance-related patterns
                                if any(pattern in content for pattern in ['@cache', '@lru_cache', 'yield', 'async def']):
                                    structure['patterns']['performance_patterns'].append({
                                        'file': rel_path,
                                        'has_caching': '@cache' in content or '@lru_cache' in content,
                                        'has_generators': 'yield' in content,
                                        'has_async': 'async def' in content
                                    })
                            
                            # Find frameworks
                            for framework in ['django', 'flask', 'fastapi', 'react', 'vue', 'angular']:
                                if framework in content.lower():
                                    structure['frameworks'].append(framework)
                                    
                    except Exception as e:
                        print(f"⚠️ Error reading file {rel_path}: {e}")
                        continue

                # Classify files
                if file.endswith(('_test.py', '.test.js', '.spec.ts')):
                    structure['test_files'].append(rel_path)
                elif file.endswith(('.json', '.yaml', '.ini', '.conf')):
                    structure['config_files'].append(rel_path)
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            structure['patterns']['configurations'].append({
                                'file': rel_path,
                                'content': content
                            })
                    except Exception as e:
                        print(f"⚠️ Error reading config file {rel_path}: {e}")
                        continue
                elif file.endswith(('.md', '.rst', '.txt')):
                    structure['doc_files'].append(rel_path)

        return structure

    def _generate_ai_rules(self, project_info: Dict[str, Any]) -> Dict[str, Any]:
        """Generate rules using Gemini AI based on project analysis."""
        try:
            # Analyze project
            project_structure = self._analyze_project_structure()
            
            # Create detailed prompt
            prompt = f"""As an AI assistant working in Cursor IDE, analyze this project to understand how you should behave and generate code that perfectly matches the project's patterns and standards.

Project Overview:
Language: {project_info.get('language', 'unknown')}
Framework: {project_info.get('framework', 'none')}
Type: {project_info.get('type', 'generic')}
Description: {project_info.get('description', 'Generic Project')}
Primary Purpose: Code generation and project analysis

Project Metrics:
- Files & Structure:
  - Total Files: {len(project_structure['files'])}
  - Test Files: {len(project_structure['test_files'])} ({len(project_structure['test_files'])/len(project_structure['files'])*100:.1f}% coverage)
  - Config Files: {len(project_structure['config_files'])}
  - Documentation: {len(project_structure['doc_files'])}
- Dependencies:
  - Frameworks: {', '.join(project_structure['frameworks']) or 'none'}
  - Core Dependencies: {', '.join(list(project_structure['dependencies'].keys())[:10])}
  - Total Dependencies: {len(project_structure['dependencies'])}

Project Ecosystem:
1. Development Environment:
- Project Structure:
{chr(10).join([f"- {f}" for f in project_structure['files'] if f.endswith(('.json', '.md', '.env', '.gitignore'))][:5])}
- IDE Configuration:
{chr(10).join([f"- {f}" for f in project_structure['files'] if '.vscode' in f or '.idea' in f][:5])}
- Build System:
{chr(10).join([f"- {f}" for f in project_structure['files'] if f in ['setup.py', 'requirements.txt', 'package.json', 'Makefile']])}

2. Project Components:
- Core Modules:
{chr(10).join([f"- {f}: {sum(1 for p in project_structure['patterns']['function_patterns'] if p['file'] == f)} functions" for f in project_structure['files'] if f.endswith('.py') and not any(x in f.lower() for x in ['test', 'setup', 'config'])][:5])}
- Support Modules:
{chr(10).join([f"- {f}" for f in project_structure['files'] if any(x in f.lower() for x in ['util', 'helper', 'common', 'shared'])][:5])}
- Templates:
{chr(10).join([f"- {f}" for f in project_structure['files'] if 'template' in f.lower()][:5])}

3. Integration Points:
- External APIs:
{chr(10).join([f"- {imp}" for imp in project_structure['patterns']['imports'] if any(api in imp.lower() for api in ['api', 'client', 'sdk', 'service'])][:5])}
- Internal Services:
{chr(10).join([f"- {imp}" for imp in project_structure['patterns']['imports'] if 'service' in imp.lower()][:5])}
- Data Storage:
{chr(10).join([f"- {f}" for f in project_structure['files'] if any(x in f.lower() for x in ['db', 'data', 'storage', 'cache'])][:5])}

4. Project Standards:
- Code Quality:
{chr(10).join([f"- {f}" for f in project_structure['files'] if f in ['.pylintrc', '.flake8', 'mypy.ini', '.eslintrc']][:5])}
- Documentation:
{chr(10).join([f"- {f}" for f in project_structure['files'] if f.endswith(('.md', '.rst', '.txt'))][:5])}
- Project Management:
{chr(10).join([f"- {f}" for f in project_structure['files'] if f in ['README.md', 'CHANGELOG.md', 'CONTRIBUTING.md', 'LICENSE']][:5])}

Code Architecture Analysis:
1. Class Structure:
- Class Hierarchy:
{chr(10).join(f"- {p['name']} ({p['inheritance'] or 'base class'})" for p in project_structure['patterns']['class_patterns'][:5])}
- Method Organization:
{chr(10).join(f"- {p['name']}: {len([m for m in project_structure['patterns']['function_patterns'] if m['file'] == p['file']])} methods" for p in project_structure['patterns']['class_patterns'][:5])}
- Common Patterns:
{chr(10).join(f"- {p['name']}: {'inherits ' + p['inheritance'] if p['inheritance'] else 'standalone'}" for p in project_structure['patterns']['class_patterns'][:5])}

2. Function Architecture:
- Signature Analysis:
{chr(10).join(f"- {p['name']}: {len(p['parameters'].split(','))} params -> {p['return_type'] or 'None'}" for p in project_structure['patterns']['function_patterns'][:5])}
- Parameter Types:
{chr(10).join(f"- {p['name']}: {p['parameters']}" for p in project_structure['patterns']['function_patterns'][:5])}
- Return Types Distribution:
{chr(10).join(f"- {p['return_type'] or 'None'}" for p in project_structure['patterns']['function_patterns'][:5])}

3. Error Handling Strategy:
- Exception Hierarchy:
{chr(10).join(f"- {p['exception_type']} ({p['file']})" for p in project_structure['patterns']['error_patterns'][:5])}
- Error Management Patterns:
{chr(10).join(f"- {p['file']}: {p['exception_type']} as {p['exception_var'] or '_'}" for p in project_structure['patterns']['error_patterns'][:5])}
- Common Error Scenarios:
{chr(10).join(f"- {p['exception_type']}: {sum(1 for e in project_structure['patterns']['error_patterns'] if e['exception_type'] == p['exception_type'])} occurrences" for p in project_structure['patterns']['error_patterns'][:5])}

4. Testing Architecture:
- Test Categories:
{chr(10).join(f"- {p['name']}: {p['parameters']}" for p in project_structure['patterns']['test_patterns'][:5])}
- Test Coverage:
{chr(10).join(f"- {file}: {sum(1 for p in project_structure['patterns']['test_patterns'] if p['file'] == file)} tests" for file in project_structure['test_files'][:5])}
- Testing Patterns:
{chr(10).join(f"- {p['name']}: {p['parameters']}" for p in project_structure['patterns']['test_patterns'][:5])}

5. Documentation Strategy:
- Docstring Analysis:
{chr(10).join(f"- {p['content'][:100]}..." for p in project_structure['patterns']['docstring_patterns'][:3])}
- Documentation Structure:
{chr(10).join(f"- {file}" for file in project_structure['doc_files'][:5])}
- Documentation Patterns:
{chr(10).join(f"- Style: {'multi-line' if len(p['content'].split(chr(10))) > 1 else 'single-line'}" for p in project_structure['patterns']['docstring_patterns'][:5])}

6. Performance Optimization:
- Caching Strategies:
{chr(10).join(f"- {p['file']}: {'uses caching' if p['has_caching'] else 'no caching'}" for p in project_structure['patterns']['performance_patterns'][:3])}
- Async Implementation:
{chr(10).join(f"- {p['file']}: {'async' if p['has_async'] else 'sync'}" for p in project_structure['patterns']['performance_patterns'][:3])}
- Resource Usage:
{chr(10).join(f"- {p['file']}: {'uses generators' if p['has_generators'] else 'standard iteration'}" for p in project_structure['patterns']['performance_patterns'][:3])}

7. Code Style Analysis:
- Naming Conventions:
{chr(10).join(f"- {p['name']}: {p['value_type']}" for p in project_structure['patterns']['variable_patterns'][:5])}
- Import Structure:
{chr(10).join(f"- {imp.split('.')[-1]}: from {'.'.join(imp.split('.')[:-1]) or 'builtin'}" for imp in project_structure['patterns']['imports'][:10])}
- Code Organization:
{chr(10).join(f"- {file.split('/')[-1]}: {sum(1 for p in project_structure['patterns']['function_patterns'] if p['file'] == file)} functions" for file in project_structure['files'][:5])}

8. Configuration Architecture:
- Config File Types:
{chr(10).join(f"- {c['file'].split('.')[-1]}: {c['file']}" for c in project_structure['patterns']['configurations'][:5])}
- Config Organization:
{chr(10).join(f"- {c['file']}: configuration file" for c in project_structure['patterns']['configurations'][:5])}
- Settings Distribution:
{chr(10).join(f"- {c['file']}: configuration settings" for c in project_structure['patterns']['configurations'][:5])}

Project Structure Layout:
1. Core Components:
{chr(10).join(f"- {file}: {sum(1 for p in project_structure['patterns']['function_patterns'] if p['file'] == file)} functions" for file in project_structure['files'][:10])}

2. Test Framework:
{chr(10).join(f"- {file}: {sum(1 for p in project_structure['patterns']['test_patterns'] if p['file'] == file)} tests" for file in project_structure['test_files'][:5])}

3. Documentation Framework:
{chr(10).join(f"- {file}: documentation" for file in project_structure['doc_files'][:5])}

4. Module Organization Analysis:
- Core Module Functions:
{chr(10).join([f"- {f}: Primary module handling {f.split('_')[0].title()} functionality" for f in project_structure['files'] if f.endswith('.py') and not any(x in f.lower() for x in ['test', 'setup', 'config'])][:5])}

- Module Dependencies:
{chr(10).join([f"- {f} depends on: {', '.join(list(set([imp.split('.')[0] for imp in project_structure['patterns']['imports'] if imp in f])))}" for f in project_structure['files'] if f.endswith('.py')][:5])}

- Module Responsibilities:
Please analyze each module's code and describe its core responsibilities based on:
1. Function and class names
2. Import statements
3. Code patterns and structures
4. Documentation strings
5. Variable names and usage
6. Error handling patterns
7. Performance optimization techniques

- Module Organization Rules:
Based on the codebase analysis, identify and describe:
1. Module organization patterns
2. Dependency management approaches
3. Code structure conventions
4. Naming conventions
5. Documentation practices
6. Testing strategies
7. Error handling strategies
8. Performance optimization patterns

Code Sample Analysis:
{chr(10).join(f"File: {file}:{chr(10)}{content[:10000]}..." for file, content in list(project_structure['code_contents'].items())[:50])}

Based on this detailed analysis, create behavior rules for AI to:
1. Replicate the project's exact code style and patterns
2. Match naming conventions precisely
3. Follow identical error handling patterns
4. Mirror the testing approach
5. Copy performance optimization techniques
6. Maintain documentation consistency
7. Apply existing security measures
8. Keep current code organization
9. Preserve module boundaries
10. Use established logging methods
11. Follow configuration patterns

Return a JSON object defining AI behavior rules:
{{"ai_behavior": {{
    "code_generation": {{
        "style": {{
            "prefer": [],
            "avoid": []
        }},
        "error_handling": {{
            "prefer": [],
            "avoid": []
        }},
        "performance": {{
            "prefer": [],
            "avoid": []
        }},
        "module_organization": {{
            "structure": [],  # Analyze and describe the current module structure
            "dependencies": [],  # Analyze actual dependencies between modules
            "responsibilities": {{}},  # Analyze and describe each module's core responsibilities
            "rules": [],  # Extract rules from actual code organization patterns
            "naming": {{}}  # Extract naming conventions from actual code
        }}
    }},
    "testing": {{
        "frameworks": [],
        "coverage_threshold": 0,
        "include": [],
        "naming": [],
        "organization": []
    }},
    "security": {{
        "sensitive_patterns": [
            "GEMINI_API_KEY",
            "API_KEY",
            "SECRET_KEY",
            "PASSWORD"
        ],
        "protected_files": [
            "config.json",
            ".env"
        ],
        "requirements": [],
        "code_review": [],
        "dependency_management": []
    }},
    "documentation": {{
        "required_sections": [
            "Project Focus",
            "Key Components",
            "Project Context",
            "Development Guidelines",
            "File Analysis",
            "Project Metrics Summary"
        ],
        "code_comments": {{
            "require_docstrings": false,
            "require_type_hints": false,
            "require_examples": false
        }}
    }}
}}}}

Critical Guidelines for AI:
1. NEVER deviate from existing code patterns
2. ALWAYS match the project's exact style
3. MAINTAIN the current complexity level
4. COPY the existing skill level approach
5. PRESERVE all established practices
6. REPLICATE the project's exact style
7. UNDERSTAND pattern purposes
8. FOLLOW existing workflows
9. RESPECT current architecture
10. MIRROR documentation style"""

            # Get AI response
            response = self.chat_session.send_message(prompt)
            
            # Extract JSON
            json_match = re.search(r'({[\s\S]*})', response.text)
            if not json_match:
                print("⚠️ No JSON found in AI response")
                raise ValueError("Invalid AI response format")
                
            json_str = json_match.group(1)
            
            try:
                ai_rules = json.loads(json_str)
                
                if not isinstance(ai_rules, dict) or 'ai_behavior' not in ai_rules:
                    print("⚠️ Invalid JSON structure in AI response")
                    raise ValueError("Invalid AI rules structure")
                    
                return ai_rules
                
            except json.JSONDecodeError as e:
                print(f"⚠️ Error parsing AI response JSON: {e}")
                raise
                
        except Exception as e:
            print(f"⚠️ Error generating AI rules: {e}")
            raise

    def generate_rules_file(self, project_info: Dict[str, Any] = None) -> str:
        """Generate the .cursorrules file based on project analysis and AI suggestions."""
        try:
            # Use analyzer if no project_info provided
            if project_info is None:
                project_info = self.analyzer.analyze_project_for_rules()
            
            # Generate AI rules
            ai_rules = self._generate_ai_rules(project_info)
            
            # Create rules with AI suggestions
            rules = {
                "version": "1.0",
                "last_updated": self._get_timestamp(),
                "project": project_info,
                "ai_behavior": ai_rules['ai_behavior']
            }
            
            # Write to file
            rules_file = os.path.join(self.project_path, '.cursorrules')
            with open(rules_file, 'w', encoding='utf-8') as f:
                json.dump(rules, f, indent=2)
            
            print("✅ Successfully generated rules using Gemini AI")
            return rules_file
                
        except Exception as e:
            print(f"❌ Failed to generate rules: {e}")
            raise 