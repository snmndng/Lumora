
from setuptools import setup, find_packages

setup(
    name="mpesa-saleor-plugin",
    version="1.0.0",
    author="Saleor Developer",
    author_email="developer@example.com",
    description="M-Pesa payment gateway plugin for Saleor",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Framework :: Django",
    ],
    python_requires=">=3.8",
    install_requires=[
        "Django>=3.2",
        "httpx>=0.24.0",
    ],
    entry_points={
        "saleor.plugins": [
            "mpesa = plugin:MpesaPaymentPlugin"
        ]
    },
    include_package_data=True,
    package_data={
        '': ['manifest.json'],
    },
)
