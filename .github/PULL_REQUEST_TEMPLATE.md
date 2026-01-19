## Description

<!-- Provide a brief description of the changes in this PR -->

## Type of Change

<!-- Mark the appropriate option with an [x] -->

- [ ] Bug fix (non-breaking change that fixes an issue)
- [ ] New feature (non-breaking change that adds functionality)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update
- [ ] Performance improvement
- [ ] Code refactoring
- [ ] CI/CD changes
- [ ] Dependency update

## Related Issues

<!-- Link any related issues here using "Fixes #issue_number" or "Relates to #issue_number" -->

Fixes #

## Changes Made

<!-- List the key changes made in this PR -->

-
-
-

## Testing

<!-- Describe the tests you ran and how to reproduce them -->

### Test Configuration

- Python version:
- Node version:
- Database: PostgreSQL 15
- Redis: 7

### Tests Performed

- [ ] Unit tests pass (`pytest` / `npm test`)
- [ ] Integration tests pass
- [ ] Linting passes (`ruff check` / `npm run lint`)
- [ ] Type checking passes (`mypy` / `npm run typecheck`)
- [ ] Manual testing completed

### Test Commands

```bash
# Backend
cd backend && uv run pytest tests/ -v

# Frontend
cd frontend && npm test
```

## Screenshots

<!-- If applicable, add screenshots to help explain your changes -->

## Checklist

<!-- Mark completed items with [x] -->

### Code Quality
- [ ] My code follows the project's style guidelines
- [ ] I have performed a self-review of my code
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] My changes generate no new warnings or errors

### Documentation
- [ ] I have updated the documentation accordingly
- [ ] I have added/updated docstrings for new/modified functions
- [ ] I have updated the README if needed

### Testing
- [ ] I have added tests that prove my fix is effective or that my feature works
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published

### Security
- [ ] I have checked for potential security vulnerabilities
- [ ] Sensitive data is not exposed in logs or error messages
- [ ] API endpoints have appropriate authentication/authorization

### Database
- [ ] Database migrations are included (if applicable)
- [ ] Migrations are backward compatible
- [ ] Indexes are added for new query patterns

### Performance
- [ ] I have considered the performance impact of my changes
- [ ] Large data operations are properly paginated/batched
- [ ] Database queries are optimized

## Deployment Notes

<!-- Any special instructions for deployment? -->

- [ ] No special deployment steps required
- [ ] Database migration required
- [ ] Environment variable changes required
- [ ] Cache invalidation required
- [ ] Other:

## Additional Notes

<!-- Any additional context or information -->
