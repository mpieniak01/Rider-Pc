# To learn more about how to use Nix to configure your environment
# see: https://firebase.google.com/docs/studio/customize-workspace
{ pkgs, ... }: {
  # Which nixpkgs channel to use.
  channel = "stable-24.05"; # or "unstable"

  # Use https://search.nixos.org/packages to find packages
  packages = [
    pkgs.python311
    pkgs.python311Packages.pip
    pkgs.python311Packages.pytest
    pkgs.nspr
    pkgs.libdrm
    pkgs.expat
    pkgs.systemd

    # System dependencies for Playwright (GUI/browser automation)
    pkgs.playwright
    pkgs.nss
    pkgs.gtk3
    pkgs.alsa-lib
    pkgs.cups
    pkgs.dbus
    pkgs.glib
    pkgs.libxkbcommon
    pkgs.pango
    pkgs.cairo
    pkgs.gdk-pixbuf
    pkgs.atk
    pkgs.at-spi2-atk
    pkgs.xorg.libX11
    pkgs.xorg.libxcb
    pkgs.xorg.libXcomposite
    pkgs.xorg.libXcursor
    pkgs.xorg.libXdamage
    pkgs.xorg.libXext
    pkgs.xorg.libXfixes
    pkgs.xorg.libXi
    pkgs.xorg.libXrandr
    pkgs.xorg.libXrender
    pkgs.mesa

    # System dependencies for ML/AI libraries from requirements.txt
    pkgs.opencv  # For mediapipe
    pkgs.espeak-ng # For piper-tts

    # Dependencies from requirements-ci.txt
    pkgs.python311Packages.fastapi
    pkgs.python311Packages.uvicorn
    pkgs.python311Packages.httpx
    pkgs.python311Packages.pyzmq
    pkgs.python311Packages.redis
    pkgs.python311Packages.celery
    pkgs.python311Packages.prometheus_client
    pkgs.python311Packages.prometheus-fastapi-instrumentator
    pkgs.python311Packages.psutil
    pkgs.python311Packages.tomli
    pkgs.python311Packages.tomli-w
    pkgs.python311Packages.google-auth
    pkgs.python311Packages.google-auth-oauthlib
    pkgs.python311Packages.google-assistant-grpc
    pkgs.python311Packages.grpcio
    pkgs.python311Packages.pillow
    pkgs.python311Packages.numpy
    pkgs.python311Packages.pytest-asyncio
    pkgs.python311Packages.pytest-timeout
    pkgs.ruff
  ];

  # Sets environment variables in the workspace
  env = {};
  idx = {
    # Search for the extensions you want on https://open-vsx.org/ and use "publisher.id"
    extensions = [
      # "vscodevim.vim"
    ];

    # Enable previews
    previews = {
      enable = true;
      previews = {
        # web = {
        #   # Example: run "npm run dev" with PORT set to IDX's defined port for previews,
        #   # and show it in IDX's web preview panel
        #   command = ["npm" "run" "dev"];
        #   manager = "web";
        #   env = {
        #     # Environment variables to set for your server
        #     PORT = "$PORT";
        #   };
        # };
      };
    };

    # Workspace lifecycle hooks
    workspace = {
      # Runs when a workspace is first created
      onCreate = {
        # Setup python virtual environment, install dependencies and playwright browsers
        install-deps = "python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt && playwright install";
      };
      # Runs when the workspace is (re)started
      onStart = {
        # Example: start a background task to watch and re-build backend code
        # watch-backend = "npm run watch-backend";
      };
    };
  };
}
