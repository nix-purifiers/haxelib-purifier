{
  description = "Locked, Nix-resolved Haxe libraries";
  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  inputs.purifier = {
    url = "github:nix-purifiers/purifier";
    flake = false;
  };
  outputs =
    {
      self,
      nixpkgs,
      purifier,
    }:
    let
      systems = [
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAll = nixpkgs.lib.genAttrs systems;
      overlay = final: prev: {
        haxelib-purifier = final.lib.makeScope final.newScope (scope: {
          nativeHaxelib = scope.callPackage ./nix/native.nix { };
          toolchain = scope.callPackage ./nix/toolchain.nix { };
          sdkVersion = import ./nix/sdk-version.nix { nixpkgsSrc = nixpkgs; };
          cli = scope.callPackage ./nix/cli.nix {
            nixpkgsSrc = nixpkgs;
            purifierSrc = purifier;
          };
          buildHaxeProject = scope.callPackage ./nix/build-project.nix {
            purifier = import (purifier + "/nix/lib") { inherit (final) lib; };
          };
        });
      };
      pkgsFor =
        system:
        import nixpkgs {
          inherit system;
          overlays = [ overlay ];
        };
    in
    {
      overlays.default = overlay;
      packages = forAll (system: {
        default = (pkgsFor system).haxelib-purifier.cli;
        cli = self.packages.${system}.default;
        sdk = (pkgsFor system).haxelib-purifier.toolchain;
      });
      lib.haxelib-purifier.readLock = import ./nix/read-lock.nix { lib = nixpkgs.lib; };
      apps = forAll (system: {
        default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/haxelib-purifier";
          meta.description = "Lock Haxe libraries";
        };
      });
      checks = forAll (
        system:
        let
          pkgs = pkgsFor system;
          build = pkgs.haxelib-purifier.buildHaxeProject { src = ./examples/minimal; };
          consumer = pkgs.writeTextDir "Consumer.hx" ''
            class Consumer {
             static function main() {
              final value=PurifierExample.answer();
              if(value != '{"answer":42}') throw value;
              Sys.println(value);
             }
            }
          '';
        in
        {
          inherit (build.packages) environment project;
          release = build.release;
          cli = self.packages.${system}.default;
          installed = pkgs.runCommand "haxe-installed-consumer" { } ''
            ${build.packages.project}/bin/haxe -cp ${consumer} -lib purifier-example --run Consumer > answer
            mkdir "$out"
            cp answer "$out/answer"
          '';
        }
      );
      formatter = forAll (system: (pkgsFor system).nixfmt-tree);
    };
}
