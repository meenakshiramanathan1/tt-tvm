#!/usr/bin/env bash
set -e # exit if a command fails

if [ -n "$CI_PROJECT_DIR" ]; then
  if [ -z $ROOT ]; then export ROOT=$CI_PROJECT_DIR; fi
else
  if [ -z $ROOT ]; then export ROOT=`git rev-parse --show-toplevel`; fi
fi

echo $ROOT
cd $ROOT
make python_env
source build/python_env/bin/activate
export TVM_HOME=$ROOT/third_party/tvm
export PYTHONPATH=$ROOT:$TVM_HOME/python:${PYTHONPATH}

# Download / untar LLVM
cd $ROOT/third_party
if [ ! -d "$ROOT/third_party/llvm" ]; then
  wget -nc https://github.com/llvm/llvm-project/releases/download/llvmorg-13.0.0/clang+llvm-13.0.0-x86_64-linux-gnu-ubuntu-20.04.tar.xz
  LLVM_TAR=$ROOT/third_party/clang+llvm-13.0.0-x86_64-linux-gnu-ubuntu-20.04.tar.xz
  LLVM_DIR=$ROOT/third_party/clang+llvm-13.0.0-x86_64-linux-gnu-ubuntu-20.04
  tar -xf $LLVM_TAR && mv $LLVM_DIR $ROOT/third_party/llvm && rm -f $LLVM_TAR
fi

cd $TVM_HOME
git submodule init; git submodule update

mkdir -p build
cp $TVM_HOME/cmake/config.cmake $TVM_HOME/build
cd $TVM_HOME/build

# Link the LLVM thats just been downloaded
LLVM_LINK=$ROOT/third_party/llvm/bin/llvm-config
sed -i "s#/usr/bin/llvm-config#$LLVM_LINK#g" $TVM_HOME/build/config.cmake

if [ "$CONFIG" == "ci" ] || [ "$CONFIG" == "" ] || [ "$CONFIG" == "release" ]; then
  export TVM_BUILD_CONFIG="Release"
else
  export TVM_BUILD_CONFIG="Debug"
fi

echo $TVM_BUILD_CONFIG
cmake -DCMAKE_BUILD_TYPE=$TVM_BUILD_CONFIG $TVM_HOME
make -j$(shell nproc)

echo "TVM Built Successful"
cd $ROOT