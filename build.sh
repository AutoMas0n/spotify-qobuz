# Navigate to CLI directory
cd cli/QobuzCliTool

# Build the solution with submodule dependency
dotnet build -c Release

# Publish standalone executable
dotnet publish -c Release -r win-x64 --self-contained true -p:PublishSingleFile=true