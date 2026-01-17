# DevOps Pipeline Setup Summary - RAG EC2 Infrastructure

## Project Overview
Design, deploy, and validate an EC2-based infrastructure for hosting a Retrieval-Augmented Generation (RAG) system using AWS CloudFormation templates with a complete CI/CD pipeline.

## AWS Infrastructure Architecture

### Core Components
- **VPC with Multi-AZ setup** - Private/public subnets for security isolation
- **Application Load Balancer (ALB)** - High availability and SSL termination
- **Auto Scaling Group** - EC2 instances running RAG application
- **Launch Template** - EC2 configuration with dynamic AMI updates
- **Target Groups** - Health checks on `/collection` endpoint
- **Security Groups** - Restrictive firewall rules

### Security Layer
- **IAM Roles** - Least privilege access (CodePipeline, CloudFormation execution roles)
- **Trust Policies** - Proper service-to-service authentication
- **S3 Bucket Policies** - Secure artifact storage

## DevOps Pipeline Architecture

### Pipeline Structure
```
Source → Build → AMI Creation → CloudFormation Deployment
```

### Stage Details

#### 1. Source Stage
- **Provider**: Amazon S3
- **Bucket**: `wattnow-ec2-deployement-bucket`
- **Object**: `template.zip` (CloudFormation template must be zipped for S3 source)
- **Output Artifact**: `dep_file`
- **Key Requirement**: S3 source requires ZIP files, not individual files

#### 2. Build Stage
- **Provider**: AWS CodeBuild
- **Purpose**: Deploy Python application to existing EC2 instance
- **Buildspec**: SSH deployment with Docker containers
- **Features**: Ollama model pulling, health checks

#### 3. AMI Creation Stage
- **Provider**: AWS CodeBuild
- **Purpose**: Create AMI from existing EC2 instance
- **Key Commands**:
  ```bash
  AMI_ID=$(aws ec2 create-image --instance-id $INSTANCE_ID --name "$AMI_NAME" --no-reboot --output text)
  aws ec2 wait image-available --image-ids $AMI_ID
  export AMI_ID=$AMI_ID
  ```
- **Exported Variables**: `AMI_ID`
- **Variable Namespace**: Must be configured in CodeBuild action

#### 4. CloudFormation Deployment Stage
- **Provider**: AWS CloudFormation
- **Template**: Dynamic AMI ID parameter
- **Parameter Override**: `{"AMIId": "#{AMIcreation.AMI_ID}"}`
- **Service Role**: `CloudFormation-EC2-ALB-Role` with EC2/ELB/AutoScaling permissions

## Key Issues Resolved

### 1. S3 Source Configuration
**Problem**: File not found in artifact
**Solution**: 
- S3 source requires ZIP files
- Zip `template.yml` → `template.zip`
- Upload ZIP to S3, reference individual file in CloudFormation action

### 2. IAM Permissions
**Problems**: 
- CodePipeline role assumption failures
- S3 access denied errors
- PassRole permission missing

**Solutions**:
- Simplified trust policy (removed conditions)
- Added S3 full access policy
- Added `iam:PassRole` permission for CloudFormation role

### 3. Dynamic AMI ID Updates
**Problem**: Hardcoded AMI ID in CloudFormation template
**Solution**:
- CloudFormation parameter: `AMIId`
- CodeBuild exported variable: `AMI_ID`
- Parameter override: `{"AMIId": "#{AMIcreation.AMI_ID}"}`
- Template reference: `ImageId: !Ref AMIId`

### 4. S3 Bucket Versioning
**Issue**: CodePipeline S3 source works better with versioned buckets
**Solution**: Enable versioning on source bucket

## CloudFormation Template Structure

### Parameters
```yaml
Parameters:
  VPCId:
    Type: String
    Default: vpc-e282698b
  SubnetId1:
    Type: String
    Default: subnet-ff5b5087
  SubnetId2:
    Type: String
    Default: subnet-66749d0f
  AMIId:
    Type: String
    Description: AMI ID from the AMI creation stage
```

### Key Resources
- **Launch Template**: Uses `!Ref AMIId` for dynamic AMI
- **Auto Scaling Group**: Min=1, Max=2, Desired=1
- **Target Group**: Health check on port 8001, path `/collection`
- **ALB**: Internet-facing, multi-AZ
- **Listener**: Port 8001, HTTP

## Pipeline Configuration Details

### CodePipeline Service Role Permissions
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": ["s3:*"],
      "Resource": ["arn:aws:s3:::wattnow-ec2-deployement-bucket/*"]
    },
    {
      "Effect": "Allow", 
      "Action": "iam:PassRole",
      "Resource": "arn:aws:iam::539279406888:role/CloudFormation-EC2-ALB-Role"
    },
    {
      "Effect": "Allow",
      "Action": "codebuild:*",
      "Resource": "arn:aws:codebuild:eu-north-1:539279406888:project/*"
    }
  ]
}
```

### CloudFormation Execution Role
**Required Policies**:
- `AmazonEC2FullAccess`
- `ElasticLoadBalancingFullAccess`
- `AutoScalingFullAccess`

## Cost Considerations
- **AMI Storage**: ~$0.23 for 1,710 GB stored for 2 hours
- **EC2 Instances**: g4dn.xlarge for GPU workloads
- **ALB**: Application Load Balancer costs
- **Auto Scaling**: Dynamic scaling based on demand

## Best Practices Implemented

### Security
- Least privilege IAM roles
- Private subnets for EC2 instances
- Security groups with minimal access
- No hardcoded credentials

### Reliability
- Multi-AZ deployment
- Auto Scaling for high availability
- Health checks and automatic recovery
- Blue/green deployment capability

### Cost Optimization
- Auto Scaling based on demand
- Spot instances consideration for cost reduction
- Resource tagging for cost tracking

## Troubleshooting Guide

### Common Issues
1. **"File does not exist in artifact"** → Check S3 source uses ZIP file
2. **"Role could not be assumed"** → Fix trust policy, remove conditions
3. **"Variable namespace does not exist"** → Configure variable namespace in CodeBuild action
4. **Stack stuck in rollback** → Wait for completion or use different stack name

### Debugging Steps
1. Check CodePipeline execution logs
2. Verify S3 bucket permissions and versioning
3. Confirm IAM role trust relationships
4. Validate CloudFormation template syntax
5. Monitor CloudWatch logs for application issues

## Future Enhancements
- **Multi-environment support** (dev/staging/prod)
- **Blue/green deployment** with CodeDeploy
- **Container-based deployment** with ECS/EKS
- **Infrastructure testing** with automated validation
- **Cost monitoring** with CloudWatch alarms
- **Security scanning** integration
# AWS CodeBuild Buildspec Documentation

## Overview
This buildspec.yml file defines the build process for deploying a FastAPI application with Ollama AI model to an EC2 instance using AWS CodeBuild.

## Build Phases

### Pre-Build Phase
**Purpose**: Environment setup and EC2 instance preparation

**Key Actions**:
- Updates system packages using yum
- Installs required tools: `jq`, `unzip`, `curl`
- Downloads and installs AWS Session Manager plugin
- Manages EC2 instance state (starts if stopped)
- Retrieves current public IP address dynamically
- Waits for SSH service readiness

**Target Instance**: `i-0a55ae2e00fb824c7`

### Build Phase
**Purpose**: Application deployment and service startup

**Deployment Process**:
1. **File Transfer**: Uses `rsync` to copy application files to EC2 (excludes key.pem)
2. **Remote Execution**: SSH connection to EC2 for service management
3. **Docker Operations**:
   - Starts and enables Docker service
   - Stops existing containers
   - Rebuilds images without cache
   - Starts services in detached mode
4. **AI Model Setup**:
   - Pulls `llama3.2:3b` model via Ollama
   - Includes wait times for service readiness

### Post-Build Phase (Commented Out)
**Purpose**: AMI creation for backup/scaling
- Creates timestamped AMI from the deployed EC2 instance
- Uses no-reboot option to maintain service availability

## Connection to the Internal Server

### SSH Connection Setup
The buildspec establishes secure connection to the EC2 instance using:
- **Private Key Authentication**: Uses `key.pem` for SSH access
- **Dynamic IP Resolution**: Automatically retrieves current public IP via AWS CLI
- **Connection Options**: 
  - `StrictHostKeyChecking=no` for automated deployment
  - `LogLevel=ERROR` to reduce verbose output

### File Transfer Process
- **Tool**: `rsync` for efficient file synchronization
- **Security**: Excludes sensitive files (key.pem) from transfer
- **Target Path**: `/home/ubuntu/app/` on the EC2 instance
- **User Context**: Connects as `ubuntu` user

### Remote Command Execution
Executes commands on EC2 via SSH heredoc:
```bash
ssh -i key.pem -o StrictHostKeyChecking=no ubuntu@$EC2_PUBLIC_IP << 'EOF'
# Commands executed remotely
EOF
```

## Key Features

### Instance Management
- Automatic EC2 instance startup if stopped
- Health checks using AWS CLI commands
- Wait conditions for proper service initialization

### Security Considerations
- SSH key exclusion from file transfers
- StrictHostKeyChecking disabled for automation
- Proper service isolation using Docker

### Service Architecture
- Docker Compose orchestration
- Ollama AI service integration
- FastAPI application deployment

## Prerequisites

### AWS Permissions Required
- EC2 instance management (start/stop/describe)
- SSM access for session management
- AMI creation permissions (if post-build enabled)

### Infrastructure Requirements
- EC2 instance with Ubuntu OS
- Docker and Docker Compose installed
- SSH access configured
- Security groups allowing required ports

### Dynamic Configuration
- `EC2_PUBLIC_IP`: Automatically retrieved from AWS API
- `INSTANCE_ID`: Hardcoded target instance identifier

## Usage Notes

### Build Artifacts
- Only `buildspec.yml` is preserved as build artifact
- Application files are deployed directly to EC2

### Timing Considerations
- 30-second wait for SSH service readiness
- 30-second wait for Ollama service startup
- 10-second final wait before status check

### Error Handling
- Graceful handling of already-running instances
- Container cleanup with `|| true` for non-critical failures
- Comprehensive logging throughout process

## Customization Points

### Instance Configuration
- Modify `INSTANCE_ID` for different target instances
- Adjust wait times based on service requirements
- Update SSH user/path as needed

### Application Deployment
- Modify rsync exclusions for different file patterns
- Update Docker Compose commands for different orchestration needs
- Customize model pulling for different AI models

### AMI Management
- Enable post-build phase for automated AMI creation
- Modify AMI naming convention as required
- Add tags or additional metadata to created AMIs
