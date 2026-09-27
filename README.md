# Unified Loop & Task Architecture

## Overview
This repository contains the architectural design and implementation of the Unified Loop & Task system, a comprehensive agentic workflow engine that manages task execution, event handling, and state management.

## Architecture Components

### Core Architecture
- **UnifiedLoop**: Main loop controller managing task lifecycle
- **TaskManager**: Task execution and coordination engine
- **EventBus**: Event-driven communication bus
- **StateManager**: State persistence and management
- **SystemIntegration**: System integration layer

### Data Layer
- **TaskStore**: Task data persistence
- **StateStore**: State data persistence
- **ConfigStore**: Configuration storage

### Integration Layer
- **Context Aggregator**: Context management and aggregation
- **Tool Manifest**: Tool registry and management
- **Agent Registry**: Agent registration and discovery

## Workflow & Lifecycle

### Task Execution Workflow
1. **Create**: Agent/user creates a task
2. **Dispatch**: UnifiedLoop dispatches task to TaskManager
3. **Execute**: TaskManager executes task handler
4. **Complete**: Task marks itself as completed
5. **Report**: System reports task status

### State Lifecycle
1. **Stopped**: Initial clean state
2. **Starting**: Boot sequence initiated
3. **Running**: Normal operation
4. **Paused**: User-initiated pause
5. **Completed**: Normal termination
6. **Error**: Error state with recovery
7. **Recovering**: Error recovery process
8. **Stopping**: Graceful shutdown
9. **Stopped**: Final clean state

## Monitoring & Management

### System Monitoring
- **Health Monitor**: System health monitoring
- **Metrics Store**: Performance metrics storage
- **Alerting**: Alert generation and notification

### Operations
- **Dashboard**: System dashboard interface
- **Operations**: Operations management console
- **Grafana**: Visualization and monitoring
- **Prometheus**: Metrics collection and storage

## Technical Specifications

### Architecture Patterns
- Event-driven architecture
- Microservices with shared state
- CQRS pattern for read/write separation
- Event sourcing for state management

### Key Features
- Fault-tolerant task execution
- Bounded retry mechanisms
- User-controllable pause/resume
- Comprehensive error recovery
- Performance monitoring and alerting

## Files & Directories

### Architecture Diagrams
- `diagrams/architecture-candidate.json`: Core architecture design
- `diagrams/workflow-candidate.json`: Task execution workflow
- `diagrams/lifecycle-candidate.json`: State lifecycle diagram
- `diagrams/monitoring-candidate.json`: System monitoring architecture
- `diagrams/management-candidate.json`: Task and loop management

### Documentation
- `ANALYSIS.md`: Technical analysis and design decisions
- `ARCHITECTURE_REFACTORING_REPORT.md`: Architecture refactoring documentation

### Implementation
- Python modules in `src/` directory
- Configuration files in `config/` directory
- Tests in `tests/` directory

## Getting Started

### Prerequisites
- Python 3.8+
- Node.js 18+
- PostgreSQL or other relational database

### Installation
```bash
pip install -r requirements.txt
npm install -g @oh-my-pi/archify
```

### Running Tests
```bash
python -m pytest tests/
npm run test:archify
```

### Development
```bash
# Development server
python -m pip install -e .
python -m src.main
```

## Architecture Validation

All architecture diagrams have been validated against the "showcase" quality profile using the Archify validation tool:

- ✅ Architecture candidate validated
- ✅ Workflow candidate validated
- ✅ Lifecycle candidate validated
- ✅ Monitoring candidate validated
- ✅ Management candidate validated

## Quality Metrics

The architecture follows these quality standards:

### Code Quality
- Clean architecture principles
- Dependency inversion
- Separation of concerns

### Performance
- Bounded resource usage
- Efficient state management
- Scalable event processing

### Reliability
- Fault tolerance
- Error recovery
- Comprehensive monitoring

## Future Directions

### Planned Enhancements
1. **Multi-tenancy support**: Support for multiple isolated environments
2. **Advanced queuing**: Prioritized task queues with dead letter handling
3. **Distributed tracing**: End-to-end observability across services
4. **AI-powered optimization**: Machine learning for task scheduling
5. **Cloud-native deployment**: Kubernetes and serverless support

### Research Areas
- Graph-based task dependency resolution
- Temporal logic for workflow specification
- Self-healing systems with autonomic computing
- Edge computing integration

## Contact & Support

For questions about the architecture or implementation:
- GitHub issues: Submit issues in this repository
- Documentation: Check the latest documentation in this repo
- Community: Join the discussion in project forums

## License

This project is licensed under the MIT License. See LICENSE file for details.
