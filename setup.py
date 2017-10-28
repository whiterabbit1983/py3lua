from setuptools import setup, find_packages


setup(
    name="py3lua",
    version='0.1',
    author="Dmitry A. Paramonov",
    author_email="asmatic075@gmail.com",
    entry_points = {
        'console_scripts': [
            'py3lua = py3lua.scripts.launcher:run'
        ],
        'setuptools.installation': [
            'py3lua_egg = py3lua.scripts.launcher:run',
        ]
    },
    packages=find_packages(
        exclude=[
            "*test*",
            "*build*",
            "*__pycache__*"
        ]
    ),
    include_package_data=True,
    description="Python to Lua source to source translator",
    long_description=open("README.md").read(),
    data_files=[(".", ["README.md", "LICENSE.txt"])],
)