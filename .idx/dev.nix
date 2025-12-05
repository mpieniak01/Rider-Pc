# To learn more about how to use Nix to configure your environment
# see: https://firebase.google.com/docs/studio/customize-workspace
{ pkgs, ... }: {
  # Which nixpkgs channel to use.
  channel = "stable-24.05"; # or "unstable"

  # Use https://search.nixos.org/packages to find packages.
  # All python packages will be auto-exposed to the shell.
  packages = with pkgs; [
    gnumake # For `make` commands
    python311 # Base Python interpreter

    # Core application dependencies (from requirements.txt)
    python311Packages.fastapi
    python311Packages.uvicorn
    python311Packages.httpx
    python311Packages.pyzmq
    python311Packages.redis
    python311Packages.celery
    python311Packages.tomli
    python311Packages.tomli-w
    (python311Packages.python-dotenv.overrideAttrs (old: {
      # Fix build issue in Nix: https://github.com/NixOS/nixpkgs/issues/231583
      postInstall = '''
        mv $out/bin/dotenv $out/bin/python-dotenv
      ''';
    }))
    python311Packages.google-auth
    python311Packages.google-auth-oauthlib
    python311Packages.google-assistant-sdk
    python311Packages.grpcio
    python311Packages.protobuf

    # Testing dependencies
    python311Packages.ruff
    python311Packages.pytest
    python311Packages.pytest-asyncio
    python311Packages.pytest-timeout
  ];

  # Sets environment variables in the workspace.
  env = {
    # Make python packages available to the interpreter.
    PYTHONPATH = "${pkgs.python311.sitePackages}";
  };

  idx = {
    # Search for the extensions you want on https://open-vsx.org/ and use "publisher.id"
    extensions = [
      # "vscodevim.vim"
    ];

    # Enable previews and configure the lightweight start command.
    previews = {
      enable = true;
      previews = {
        web = {
          command = ["make" "start-dev"];
          manager = "web";
        };
      };
    };

    # Workspace lifecycle hooks.
    # `onCreate` is removed as Nix now handles all installations.
    workspace = {
      onStart = {
        # Example: start a background task to watch and re-build backend code
        # watch-backend = "npm run watch-backend";
      };
    };
  };
}
