import setuptools

with open("sql_refactor/README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="sql-refactor",
    version="0.0.1",
    author="Muhamad Tohir",
    author_email="maztohir@gmail.com",
    description="Transform column and table name to desired one",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/maztohir/sample-sql-translator",
    project_urls={
        "Bug Tracker": "https://github.com/maztohir/sample-sql-translator/issues",
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    package_dir={"": "sql_refactor"},
    # packages=setuptools.find_packages(where="sql_refactor"),
    python_requires=">=3.7.9",
)