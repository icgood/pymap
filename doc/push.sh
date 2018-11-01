#!/usr/bin/env bash
set -e

repo_dir=$(pwd)
pushd doc
make clean html
popd

cd ..
git clone -b gh-pages "https://$GH_TOKEN@github.com/icgood/pymap.git" gh-pages
cd gh-pages

if [ "$1" != "dry" ]; then
    git config user.name "Travis Builder"
    git config user.email "icgood@gmail.com"
fi

cp -R $repo_dir/doc/build/html/* ./
touch .nojekyll

# Add and commit changes.
git add -A .
git commit -m "Autodoc commit for $COMMIT."
if [ "$1" != "dry" ]; then
    # -q is very important, otherwise you leak your GH_TOKEN
    git push -q origin gh-pages
fi
