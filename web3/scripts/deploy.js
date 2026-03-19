const hre = require("hardhat");
const fs = require("fs");
const path = require("path");

async function main() {
  console.log("🚀 Starting Fibtool contract deployment to", hre.network.name);
  console.log("=".repeat(60));

  const [deployer] = await hre.ethers.getSigners();
  console.log("📝 Deploying contracts with account:", deployer.address);
  
  const balance = await hre.ethers.provider.getBalance(deployer.address);
  console.log("💰 Account balance:", hre.ethers.formatEther(balance), "ETH");
  console.log("=".repeat(60));

  const deployedContracts = {};

  // 1. Deploy FIBT Token
  console.log("\n1️⃣  Deploying FIBTToken...");
  const FIBTToken = await hre.ethers.getContractFactory("FIBTToken");
  const fibtToken = await FIBTToken.deploy();
  await fibtToken.waitForDeployment();
  const fibtTokenAddress = await fibtToken.getAddress();
  deployedContracts.FIBTToken = fibtTokenAddress;
  console.log("✅ FIBTToken deployed to:", fibtTokenAddress);

  // 2. Deploy Strategy NFT
  console.log("\n2️⃣  Deploying StrategyNFT...");
  const StrategyNFT = await hre.ethers.getContractFactory("StrategyNFT");
  const strategyNFT = await StrategyNFT.deploy();
  await strategyNFT.waitForDeployment();
  const strategyNFTAddress = await strategyNFT.getAddress();
  deployedContracts.StrategyNFT = strategyNFTAddress;
  console.log("✅ StrategyNFT deployed to:", strategyNFTAddress);

  // 3. Deploy Staking Manager
  console.log("\n3️⃣  Deploying StakingManager...");
  const StakingManager = await hre.ethers.getContractFactory("StakingManager");
  const stakingManager = await StakingManager.deploy(fibtTokenAddress);
  await stakingManager.waitForDeployment();
  const stakingManagerAddress = await stakingManager.getAddress();
  deployedContracts.StakingManager = stakingManagerAddress;
  console.log("✅ StakingManager deployed to:", stakingManagerAddress);

  // 4. Deploy VIP Tier Manager
  console.log("\n4️⃣  Deploying VIPTierManager...");
  const VIPTierManager = await hre.ethers.getContractFactory("VIPTierManager");
  const vipTierManager = await VIPTierManager.deploy(fibtTokenAddress);
  await vipTierManager.waitForDeployment();
  const vipTierManagerAddress = await vipTierManager.getAddress();
  deployedContracts.VIPTierManager = vipTierManagerAddress;
  console.log("✅ VIPTierManager deployed to:", vipTierManagerAddress);

  // 5. Deploy Price Oracle
  console.log("\n5️⃣  Deploying PriceOracle...");
  const PriceOracle = await hre.ethers.getContractFactory("PriceOracle");
  const priceOracle = await PriceOracle.deploy();
  await priceOracle.waitForDeployment();
  const priceOracleAddress = await priceOracle.getAddress();
  deployedContracts.PriceOracle = priceOracleAddress;
  console.log("✅ PriceOracle deployed to:", priceOracleAddress);

  // 6. Deploy MT5 Oracle
  console.log("\n6️⃣  Deploying MT5Oracle...");
  const MT5Oracle = await hre.ethers.getContractFactory("MT5Oracle");
  const mt5Oracle = await MT5Oracle.deploy();
  await mt5Oracle.waitForDeployment();
  const mt5OracleAddress = await mt5Oracle.getAddress();
  deployedContracts.MT5Oracle = mt5OracleAddress;
  console.log("✅ MT5Oracle deployed to:", mt5OracleAddress);

  // 7. Deploy Performance Verifier
  console.log("\n7️⃣  Deploying PerformanceVerifier...");
  const PerformanceVerifier = await hre.ethers.getContractFactory("PerformanceVerifier");
  const performanceVerifier = await PerformanceVerifier.deploy(
    mt5OracleAddress,
    priceOracleAddress
  );
  await performanceVerifier.waitForDeployment();
  const performanceVerifierAddress = await performanceVerifier.getAddress();
  deployedContracts.PerformanceVerifier = performanceVerifierAddress;
  console.log("✅ PerformanceVerifier deployed to:", performanceVerifierAddress);

  // 8. Deploy Strategy Registry
  console.log("\n8️⃣  Deploying StrategyRegistry...");
  const StrategyRegistry = await hre.ethers.getContractFactory("StrategyRegistry");
  const strategyRegistry = await StrategyRegistry.deploy(
    strategyNFTAddress,
    performanceVerifierAddress
  );
  await strategyRegistry.waitForDeployment();
  const strategyRegistryAddress = await strategyRegistry.getAddress();
  deployedContracts.StrategyRegistry = strategyRegistryAddress;
  console.log("✅ StrategyRegistry deployed to:", strategyRegistryAddress);

  // 9. Deploy Signal Escrow
  console.log("\n9️⃣  Deploying SignalEscrow...");
  const SignalEscrow = await hre.ethers.getContractFactory("SignalEscrow");
  const signalEscrow = await SignalEscrow.deploy(
    fibtTokenAddress,
    strategyRegistryAddress,
    vipTierManagerAddress
  );
  await signalEscrow.waitForDeployment();
  const signalEscrowAddress = await signalEscrow.getAddress();
  deployedContracts.SignalEscrow = signalEscrowAddress;
  console.log("✅ SignalEscrow deployed to:", signalEscrowAddress);

  // 10. Deploy Revenue Distributor
  console.log("\n🔟 Deploying RevenueDistributor...");
  const RevenueDistributor = await hre.ethers.getContractFactory("RevenueDistributor");
  const revenueDistributor = await RevenueDistributor.deploy(
    fibtTokenAddress,
    stakingManagerAddress
  );
  await revenueDistributor.waitForDeployment();
  const revenueDistributorAddress = await revenueDistributor.getAddress();
  deployedContracts.RevenueDistributor = revenueDistributorAddress;
  console.log("✅ RevenueDistributor deployed to:", revenueDistributorAddress);

  // 11. Deploy Governance DAO
  console.log("\n1️⃣1️⃣  Deploying GovernanceDAO...");
  const GovernanceDAO = await hre.ethers.getContractFactory("GovernanceDAO");
  const governanceDAO = await GovernanceDAO.deploy(fibtTokenAddress);
  await governanceDAO.waitForDeployment();
  const governanceDAOAddress = await governanceDAO.getAddress();
  deployedContracts.GovernanceDAO = governanceDAOAddress;
  console.log("✅ GovernanceDAO deployed to:", governanceDAOAddress);

  console.log("\n" + "=".repeat(60));
  console.log("🎉 All contracts deployed successfully!");
  console.log("=".repeat(60));

  // Post-deployment configuration
  console.log("\n⚙️  Configuring contracts...");

  // Grant MINTER_ROLE to StrategyRegistry on StrategyNFT
  console.log("- Granting MINTER_ROLE to StrategyRegistry...");
  const MINTER_ROLE = await strategyNFT.MINTER_ROLE();
  await strategyNFT.grantRole(MINTER_ROLE, strategyRegistryAddress);
  console.log("✅ Role granted");

  // Whitelist SignalEscrow for token transfers
  console.log("- Whitelisting SignalEscrow...");
  await fibtToken.updateWhitelist(signalEscrowAddress, true);
  console.log("✅ Whitelisted");

  // Whitelist RevenueDistributor for token transfers
  console.log("- Whitelisting RevenueDistributor...");
  await fibtToken.updateWhitelist(revenueDistributorAddress, true);
  console.log("✅ Whitelisted");

  // Whitelist StakingManager for token transfers
  console.log("- Whitelisting StakingManager...");
  await fibtToken.updateWhitelist(stakingManagerAddress, true);
  console.log("✅ Whitelisted");

  console.log("\n✅ Configuration complete!");

  // Save deployment addresses
  const deploymentInfo = {
    network: hre.network.name,
    chainId: (await hre.ethers.provider.getNetwork()).chainId.toString(),
    deployer: deployer.address,
    timestamp: new Date().toISOString(),
    contracts: deployedContracts,
    gasUsed: "Check block explorer for accurate gas usage",
  };

  const deploymentsDir = path.join(__dirname, "../deployments");
  if (!fs.existsSync(deploymentsDir)) {
    fs.mkdirSync(deploymentsDir);
  }

  const filename = `${hre.network.name}-${Date.now()}.json`;
  fs.writeFileSync(
    path.join(deploymentsDir, filename),
    JSON.stringify(deploymentInfo, null, 2)
  );

  console.log("\n📄 Deployment info saved to:", filename);

  // Print summary
  console.log("\n" + "=".repeat(60));
  console.log("📊 DEPLOYMENT SUMMARY");
  console.log("=".repeat(60));
  console.log("Network:", hre.network.name);
  console.log("Chain ID:", deploymentInfo.chainId);
  console.log("Deployer:", deployer.address);
  console.log("\n📝 Contract Addresses:");
  console.log("=".repeat(60));
  
  Object.entries(deployedContracts).forEach(([name, address], index) => {
    console.log(`${index + 1}. ${name.padEnd(25)} ${address}`);
  });

  console.log("\n" + "=".repeat(60));
  console.log("⚠️  IMPORTANT: Save these addresses!");
  console.log("=".repeat(60));
  console.log("\n📋 Next Steps:");
  console.log("1. Update frontend .env.local with contract addresses");
  console.log("2. Verify contracts on Arbiscan: npm run verify:testnet");
  console.log("3. Enable trading: fibtToken.enableTrading()");
  console.log("4. Test all contract interactions");
  console.log("5. Deploy frontend with updated addresses");
  console.log("\n✨ Deployment complete! ✨\n");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error("\n❌ Deployment failed:", error);
    process.exit(1);
  });
