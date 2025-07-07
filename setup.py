"""Setup script for Playwright AI."""

from setuptools import setup, find_packages

# Read requirements
with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="playwright-ai",
    version="0.1.0",
    author="Playwright AI Contributors",
    description="AI-powered browser automation for Python",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/your-org/playwright-ai",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.9",
    install_requires=[
        "playwright>=1.40.0",
        "pydantic>=2.5.0",
        "python-dotenv>=1.0.0",
        "structlog>=24.1.0",
        "httpx>=0.25.0",
        "openai>=1.6.0",
        "anthropic>=0.8.0",
        "google-generativeai>=0.3.0",
        "langchain>=0.1.0",
        "filelock>=3.13.0",
        "aiofiles>=23.2.0",
    ],
)