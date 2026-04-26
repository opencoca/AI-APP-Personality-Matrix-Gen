# Homebrew formula for yt-analyst.
#
# To publish:
#   1. Run: make release VERSION=x.y.z && git push --tags
#   2. Download the release tarball and compute:
#        curl -sL https://github.com/Startr/AI-APP-Personality-Matrix-Gen/archive/refs/tags/vX.Y.Z.tar.gz | sha256sum
#   3. Replace FILL_IN_ON_RELEASE below with the SHA256.
#   4. Update resource SHA256s by running:
#        brew update-python-resources Formula/yt-analyst.rb
#   5. Copy this file to your Homebrew tap repo (e.g. Startr/homebrew-tools/Formula/).
#   6. Users install with: brew tap Startr/tools && brew install yt-analyst
#
# After first install, add MCP credentials to ~/.config/vault/secrets:
#   echo 'YT_ANALYST_MCP_URL=https://your-tunnel-url.trycloudflare.com' >> ~/.config/vault/secrets
#   echo 'YT_ANALYST_MCP_TOKEN=your-token-here' >> ~/.config/vault/secrets
#
# Per-project override: create a .env file in your working directory with the same keys.

class YtAnalyst < Formula
  include Language::Python::Virtualenv

  desc "YouTube channel transcript archiver and voice/personality profiler for Sage.is personas"
  homepage "https://github.com/Startr/AI-APP-Personality-Matrix-Gen"
  url "https://github.com/Startr/AI-APP-Personality-Matrix-Gen/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "FILL_IN_ON_RELEASE"
  license "AGPL-3.0-or-later"
  head "https://github.com/Startr/AI-APP-Personality-Matrix-Gen.git", branch: "main"

  depends_on "python@3.12"
  depends_on "yt-dlp"  # used via subprocess — system dep, not a Python resource

  # Run `brew update-python-resources Formula/yt-analyst.rb` to regenerate these
  resource "requests" do
    url "https://files.pythonhosted.org/packages/FILL_IN/requests-2.32.3.tar.gz"
    sha256 "FILL_IN_ON_RELEASE"
  end

  resource "pyyaml" do
    url "https://files.pythonhosted.org/packages/FILL_IN/PyYAML-6.0.2.tar.gz"
    sha256 "FILL_IN_ON_RELEASE"
  end

  resource "feedparser" do
    url "https://files.pythonhosted.org/packages/FILL_IN/feedparser-6.0.11.tar.gz"
    sha256 "FILL_IN_ON_RELEASE"
  end

  # requests transitive deps
  resource "certifi" do
    url "https://files.pythonhosted.org/packages/FILL_IN/certifi-2024.12.14.tar.gz"
    sha256 "FILL_IN_ON_RELEASE"
  end

  resource "charset-normalizer" do
    url "https://files.pythonhosted.org/packages/FILL_IN/charset_normalizer-3.4.1.tar.gz"
    sha256 "FILL_IN_ON_RELEASE"
  end

  resource "idna" do
    url "https://files.pythonhosted.org/packages/FILL_IN/idna-3.10.tar.gz"
    sha256 "FILL_IN_ON_RELEASE"
  end

  resource "urllib3" do
    url "https://files.pythonhosted.org/packages/FILL_IN/urllib3-2.3.0.tar.gz"
    sha256 "FILL_IN_ON_RELEASE"
  end

  # feedparser transitive dep
  resource "sgmllib3k" do
    url "https://files.pythonhosted.org/packages/FILL_IN/sgmllib3k-1.0.0.tar.gz"
    sha256 "FILL_IN_ON_RELEASE"
  end

  def install
    virtualenv_install_with_resources
  end

  def post_install
    (var/"yt-analyst").mkpath
  end

  def caveats
    <<~EOS
      Add your MCP credentials to ~/.config/vault/secrets (if not already present):
        echo 'YT_ANALYST_MCP_URL=https://your-tunnel-url.trycloudflare.com' >> ~/.config/vault/secrets
        echo 'YT_ANALYST_MCP_TOKEN=your-token-here' >> ~/.config/vault/secrets

      To override per-project, create a .env file in your working directory:
        echo 'YT_ANALYST_MCP_URL=https://...' > .env
        echo 'YT_ANALYST_MCP_TOKEN=...' >> .env

      Config priority: project .env > ~/.config/vault/secrets > legacy YAML configs

      Then get started:
        yt-analyst discover https://www.youtube.com/@YourChannel
    EOS
  end

  test do
    assert_match "yt-analyst", shell_output("#{bin}/yt-analyst --help")
    assert_match version.to_s, shell_output("#{bin}/yt-analyst --version")
  end
end
