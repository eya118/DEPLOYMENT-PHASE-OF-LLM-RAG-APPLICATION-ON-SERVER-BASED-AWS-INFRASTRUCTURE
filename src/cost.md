# AWS Cost Documentation - EC2 Auto Scaling with ALB

## Resource Overview
This document outlines the costs for the EC2 Auto Scaling with Application Load Balancer setup deployed in **EU-North-1 (Stockholm)** region.

## Current Configuration
- **Min Instances**: 1
- **Max Instances**: 2  
- **Desired Capacity**: 1
- **Instance Type**: g4dn.xlarge
- **Region**: eu-north-1

## Cost Breakdown

### 1. EC2 Instances (g4dn.xlarge)
- **Instance Type**: g4dn.xlarge (GPU instance)
- **vCPUs**: 4
- **Memory**: 16 GB
- **GPU**: 1x NVIDIA T4
- **Storage**: 125 GB NVMe SSD

**Pricing (EU-North-1)**:
- **On-Demand**: ~$0.526/hour
- **Monthly (1 instance)**: ~$383/month (24/7)
- **Monthly (2 instances)**: ~$766/month (if scaled up)

### 2. Application Load Balancer (ALB)
- **Fixed Cost**: ~$16.20/month
- **Load Balancer Capacity Units (LCU)**: $0.008/hour per LCU
- **Estimated LCU cost**: ~$5-10/month (low traffic)

### 3. Data Transfer
- **Data Transfer Out**: $0.09/GB (first 10TB)
- **Data Transfer In**: Free
- **Estimated**: $5-20/month (depends on usage)

### 4. EBS Storage
- **Launch Template Storage**: 125 GB NVMe SSD (included with instance)
- **Additional EBS**: $0.119/GB/month (if added)

## Total Monthly Cost Estimates

### Low Load Scenario (1 instance running)
| Resource | Cost |
|----------|------|
| EC2 g4dn.xlarge (1 instance) | $383/month |
| Application Load Balancer | $21/month |
| Data Transfer | $10/month |
| **Total** | **~$414/month** |

### High Load Scenario (2 instances running)
| Resource | Cost |
|----------|------|
| EC2 g4dn.xlarge (2 instances) | $766/month |
| Application Load Balancer | $21/month |
| Data Transfer | $15/month |
| **Total** | **~$802/month** |

## Cost Optimization Tips

### 1. Auto Scaling Benefits
- **Pay only for running instances**
- Scales down during low usage
- Scales up only when needed

### 2. Reserved Instances
- **1-year term**: ~30% savings
- **3-year term**: ~50% savings
- **Estimated savings**: $115-190/month per instance

### 3. Spot Instances
- **Savings**: Up to 70% off On-Demand
- **Risk**: Can be terminated with 2-minute notice
- **Not recommended** for production Ollama servers

### 4. Scheduled Scaling
- Scale down during off-hours
- Use CloudWatch Events for automation
- **Potential savings**: 30-50% if predictable usage

## Monitoring Costs
- **CloudWatch**: ~$3-5/month for basic metrics
- **AWS Cost Explorer**: Free
- **Billing Alerts**: Free

## Free Tier (Not Applicable)
- g4dn.xlarge is **not eligible** for AWS Free Tier
- Free Tier only covers t2.micro/t3.micro instances

## Cost Alerts Recommendation
Set up billing alerts for:
- **$400/month** (normal usage)
- **$600/month** (high usage warning)
- **$800/month** (maximum expected)

## Notes
- Prices are estimates based on EU-North-1 region
- Actual costs may vary based on usage patterns
- GPU instances are expensive but necessary for AI workloads
- Consider using smaller instances (t3.medium) if GPU not required

## Last Updated
Date: Current deployment
Region: eu-north-1
Instance Type: g4dn.xlarge