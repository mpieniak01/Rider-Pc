{
  pkgs,
  ...
}: {
  channel = "unstable";
  packages = with pkgs; [
    gnumake
    python311
    python311Packages.pip
    python311Packages.fastapi
    python311Packages.uvicorn
    python311Packages.httpx
    python311Packages.pyzmq
    python311Packages.redis
    python311Packages.celery
    python311Packages.tomli
    python311Packages.tomli-w
    (python311Packages.python-dotenv.overrideAttrs (old: {
      postInstall = ''
        mv $out/bin/dotenv $out/bin/python-dotenv
      '';
    }))
    python311Packages.google-auth
    python311Packages.google-auth-oauthlib
    python311Packages.grpcio
    python311Packages.protobuf
    python311Packages.prometheus-client
    python311Packages.prometheus-fastapi-instrumentator
    python311Packages.psutil
    python311Packages.openai-whisper
    python311Packages.ultralytics
    python311Packages.pillow
    python311Packages.numpy
    python311Packages.torch
    piper-tts
    python311Packages.ollama
    python311Packages.mediapipe
    python311Packages.chromadb
    python311Packages.sentence-transformers
    ruff
    python311Packages.pytest
    python311Packages.pytest-asyncio
    python311Packages.pytest-timeout
  ];
  env = {
    PYTHONPATH = "${pkgs.python311.sitePackages}";
  };
  idx = {
    extensions = [];
    previews = {
      enable = true;
      previews = {
        web = {
          command = [ "make" "start-dev" ];
          manager = "web";
        };
      };
    };
    workspace = {
      # Uruchom instalację lokalnych pakietów przy starcie środowiska
      onStart = {
        install-local-deps = "echo 'Instalowanie lokalnych zależności Python...' && pip install -r requirements-local.txt";
      };
    };
  };
}
