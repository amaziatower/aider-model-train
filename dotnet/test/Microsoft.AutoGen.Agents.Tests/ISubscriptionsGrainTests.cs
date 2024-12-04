// Copyright (c) Microsoft Corporation. All rights reserved.
// ISubscriptionsGrainTests.cs

using Moq;
using Xunit;

namespace Microsoft.AutoGen.Agents.Tests;

public class ISubscriptionsGrainTests
{
    private readonly Mock<ISubscriptionsGrain> _mockSubscriptionsGrain;

    public ISubscriptionsGrainTests()
    {
        _mockSubscriptionsGrain = new Mock<ISubscriptionsGrain>();
    }

    [Fact]
    public async Task GetSubscriptions_ReturnsAllSubscriptions_WhenAgentTypeIsNull()
    {
        // Arrange
        var subscriptions = new Dictionary<string, List<string>>
        {
            { "topic1", new List<string> { "agentType1" } },
            { "topic2", new List<string> { "agentType2" } }
        };
        _mockSubscriptionsGrain.Setup(grain => grain.GetSubscriptions(null)).ReturnsAsync(subscriptions);

        // Act
        var result = await _mockSubscriptionsGrain.Object.GetSubscriptions();

        // Assert
        Assert.Equal(2, result.Count);
        Assert.Contains("topic1", result.Keys);
        Assert.Contains("topic2", result.Keys);
    }

    [Fact]
    public async Task GetSubscriptions_ReturnsFilteredSubscriptions_WhenAgentTypeIsNotNull()
    {
        // Arrange
        var subscriptions = new Dictionary<string, List<string>>
        {
            { "topic1", new List<string> { "agentType1" } }
        };
        _mockSubscriptionsGrain.Setup(grain => grain.GetSubscriptions("agentType1")).ReturnsAsync(subscriptions);

        // Act
        var result = await _mockSubscriptionsGrain.Object.GetSubscriptions("agentType1");

        // Assert
        Assert.Single(result);
        Assert.Contains("topic1", result.Keys);
    }

    [Fact]
    public async Task SubscribeAsync_AddsSubscription()
    {
        // Arrange
        _mockSubscriptionsGrain.Setup(grain => grain.SubscribeAsync("agentType1", "topic1")).Returns(ValueTask.CompletedTask);

        // Act
        await _mockSubscriptionsGrain.Object.SubscribeAsync("agentType1", "topic1");

        // Assert
        _mockSubscriptionsGrain.Verify(grain => grain.SubscribeAsync("agentType1", "topic1"), Times.Once);
    }

    [Fact]
    public async Task UnsubscribeAsync_RemovesSubscription()
    {
        // Arrange
        _mockSubscriptionsGrain.Setup(grain => grain.UnsubscribeAsync("agentType1", "topic1")).Returns(ValueTask.CompletedTask);

        // Act
        await _mockSubscriptionsGrain.Object.UnsubscribeAsync("agentType1", "topic1");

        // Assert
        _mockSubscriptionsGrain.Verify(grain => grain.UnsubscribeAsync("agentType1", "topic1"), Times.Once);
    }
}