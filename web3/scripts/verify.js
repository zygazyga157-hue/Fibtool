const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("🔍 Starting contract verification...\n");

  // Read latest deployment file
  const deploymentsDir = path.join(__dirname, "../deployments");
  const files = fs.readdirSync(deploymentsDir);
  const latestFile = files
    .filter(f => f.startsWith(hre.network.name))
    .sort()
    .reverse()[0];

  if (!latestFile) {
    console.error("❌ No deployment file found for", hre.network.name);
    process.exit(1);
  }

  const deployment = JSON.parse(
    fs.readFileSync(path.join(deploymentsDir, latestFile), "utf8")
  );

  console.log("📄 Using deployment file:", latestFile);
  console.log("Network:", deployment.network);
  console.log("=".repeat(60), "\n");

  const contracts = deployment.contracts;

  // 1. Verify FIBTToken
  try {
    console.log("1️⃣  Verifying FIBTToken...");
    await hre.run("verify:verify", {
      address: contracts.FIBTToken,
      constructorArguments: [],
    });
    console.log("✅ Verified\n");
  } catch (error) {
    console.log("⚠️  Already verified or error:", error.message, "\n");
  }

  // 2. Verify StrategyNFT
  try {
    console.log("2️⃣  Verifying StrategyNFT...");
    await hre.run("verify:verify", {
      address: contracts.StrategyNFT,
      constructorArguments: [],
    });
    console.log("✅ Verified\n");
  } catch (error) {
    console.log("⚠️  Already verified or error:", error.message, "\n");
  }

  // 3. Verify StakingManager
  try {
    console.log("3️⃣  Verifying StakingManager...");
    await hre.run("verify:verify", {
      address: contracts.StakingManager,
      constructorArguments: [contracts.FIBTToken],
    });
    console.log("✅ Verified\n");
  } catch (error) {
    console.log("⚠️  Already verified or error:", error.message, "\n");
  }

  // 4. Verify VIPTierManager
  try {
    console.log("4️⃣  Verifying VIPTierManager...");
    await hre.run("verify:verify", {
      address: contracts.VIPTierManager,
      constructorArguments: [contracts.FIBTToken],
    });
    console.log("✅ Verified\n");
  } catch (error) {
    console.log("⚠️  Already verified or error:", error.message, "\n");
  }

  // 5. Verify PriceOracle
  try {
    console.log("5️⃣  Verifying PriceOracle...");
    await hre.run("verify:verify", {
      address: contracts.PriceOracle,
      constructorArguments: [],
    });
    console.log("✅ Verified\n");
  } catch (error) {
    console.log("⚠️  Already verified or error:", error.message, "\n");
  }

  // 6. Verify MT5Oracle
  try {
    console.log("6️⃣  Verifying MT5Oracle...");
    await hre.run("verify:verify", {
      address: contracts.MT5Oracle,
      constructorArguments: [],
    });
    console.log("✅ Verified\n");
  } catch (error) {
    console.log("⚠️  Already verified or error:", error.message, "\n");
  }

  // 7. Verify PerformanceVerifier
  try {
    console.log("7️⃣  Verifying PerformanceVerifier...");
    await hre.run("verify:verify", {
      address: contracts.PerformanceVerifier,
      constructorArguments: [contracts.MT5Oracle, contracts.PriceOracle],
    });
    console.log("✅ Verified\n");
  } catch (error) {
    console.log("⚠️  Already verified or error:", error.message, "\n");
  }

  // 8. Verify StrategyRegistry
  try {
    console.log("8️⃣  Verifying StrategyRegistry...");
    await hre.run("verify:verify", {
      address: contracts.StrategyRegistry,
      constructorArguments: [contracts.StrategyNFT, contracts.PerformanceVerifier],
    });
    console.log("✅ Verified\n");
  } catch (error) {
    console.log("⚠️  Already verified or error:", error.message, "\n");
  }

  // 9. Verify SignalEscrow
  try {
    console.log("9️⃣  Verifying SignalEscrow...");
    await hre.run("verify:verify", {
      address: contracts.SignalEscrow,
      constructorArguments: [
        contracts.FIBTToken,
        contracts.StrategyRegistry,
        contracts.VIPTierManager,
      ],
    });
    console.log("✅ Verified\n");
  } catch (error) {
    console.log("⚠️  Already verified or error:", error.message, "\n");
  }

  // 10. Verify RevenueDistributor
  try {
    console.log("🔟 Verifying RevenueDistributor...");
    await hre.run("verify:verify", {
      address: contracts.RevenueDistributor,
      constructorArguments: [contracts.FIBTToken, contracts.StakingManager],
    });
    console.log("✅ Verified\n");
  } catch (error) {
    console.log("⚠️  Already verified or error:", error.message, "\n");
  }

  // 11. Verify GovernanceDAO
  try {
    console.log("1️⃣1️⃣  Verifying GovernanceDAO...");
    await hre.run("verify:verify", {
      address: contracts.GovernanceDAO,
      constructorArguments: [contracts.FIBTToken],
    });
    console.log("✅ Verified\n");
  } catch (error) {
    console.log("⚠️  Already verified or error:", error.message, "\n");
  }

  console.log("=".repeat(60));
  console.log("✅ Verification process complete!");
  console.log("=".repeat(60));
  console.log("\n📊 View contracts on Arbiscan:");
  console.log(`https://${hre.network.name === 'arbitrumSepolia' ? 'sepolia.' : ''}arbiscan.io/address/${contracts.FIBTToken}\n`);
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("❌ Verification failed:", error);
    process.exit(1);
  });
