from setuptools import find_packages, setup

setup(
    name="source_facebook_organic",
    version="0.1.0",
    description="Conector Airbyte para conteúdo orgânico de páginas do Facebook",
    author="Binder",
    packages=find_packages(exclude=("tests",)),
    install_requires=["airbyte-cdk>=7,<8"],
    package_data={"": ["*.json", "schemas/*.json"]},
    entry_points={"console_scripts": ["source-facebook-organic=source_facebook_organic.run:run"]},
)
